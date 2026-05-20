"""
수급 분석 서비스

pykrx를 통해 투자자별(외국인/기관/개인) 순매수 데이터를 수집하고
수급 흐름을 분석합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 모든 결과는 참고용 수급 흐름 정보입니다.
"""
import json
import logging
import time
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.sql import func as _sf

from app.config import settings
from app.database import get_db_session
from app.models.supply_demand_analysis import SupplyDemandAnalysis

logger = logging.getLogger(__name__)

DISCLAIMER = "본 수급 분석은 참고용이며 투자 권유가 아닙니다."
BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

# ── pykrx 데이터 수집 ───────────────────────────────────────────

def _to_date_str(d: date) -> str:
    return d.strftime("%Y%m%d")


def _fetch_investor_trading(stock_code: str, end_date: date,
                            lookback: int = 20) -> Optional[pd.DataFrame]:
    """pykrx: 투자자별 순매수 금액 (최근 lookback 영업일)."""
    import contextlib
    import io
    import logging

    from app.utils.pykrx_lock import _lock as _pykrx_lock
    from pykrx import stock as pk

    logging.getLogger("pykrx").setLevel(logging.CRITICAL)

    start = end_date - timedelta(days=lookback * 2 + 10)
    try:
        with _pykrx_lock:
            with contextlib.redirect_stdout(io.StringIO()):
                df = pk.get_market_trading_value_by_date(
                    _to_date_str(start), _to_date_str(end_date), stock_code
                )
        if df is None or df.empty:
            return None
        # 위치 기반으로 컬럼명 통일 (인코딩 무관)
        cols = list(df.columns)
        rename = {}
        for c in cols:
            decoded = c if isinstance(c, str) else c.decode("utf-8", errors="replace")
            if "기관" in decoded:
                rename[c] = "institution"
            elif "외국" in decoded:
                rename[c] = "foreign"
            elif "개인" in decoded:
                rename[c] = "individual"
            elif "전체" in decoded or "합계" in decoded:
                rename[c] = "total"
        df = df.rename(columns=rename)
        # 인식 안 된 컬럼 제거
        df = df[[c for c in ["institution", "foreign", "individual", "total"] if c in df.columns]]
        return df.tail(lookback)
    except Exception as e:
        logger.warning(f"[수급] {stock_code} 투자자 데이터 수집 실패: {e}")
        return None


def _fetch_short_sell(stock_code: str, end_date: date) -> tuple[float, int]:
    """pykrx: 공매도 비중(%) 및 수량."""
    import contextlib
    import io

    from app.utils.pykrx_lock import _lock as _pykrx_lock
    from pykrx import stock as pk

    start = end_date - timedelta(days=15)
    try:
        with _pykrx_lock:
            with contextlib.redirect_stdout(io.StringIO()):
                df = pk.get_shorting_volume_by_date(
                    _to_date_str(start), _to_date_str(end_date), stock_code
                )
        if df is None or df.empty:
            return 0.0, 0
        latest = df.iloc[-1]
        # 컬럼명 위치 기반 탐색
        vals = list(latest.values)
        # 공매도수량, 매수수량, 비중 순서로 반환됨
        ratio = float(vals[2]) if len(vals) >= 3 else 0.0
        vol   = int(vals[0])   if len(vals) >= 1 else 0
        return ratio, vol
    except Exception as e:
        logger.warning(f"[수급] {stock_code} 공매도 데이터 수집 실패: {e}")
        return 0.0, 0


# ── 지표 계산 ───────────────────────────────────────────────────

def _calc_streak(series: pd.Series) -> int:
    """연속 순매수(양수) 또는 순매도(음수) 일수 반환."""
    if series.empty:
        return 0
    vals = series.values
    last = vals[-1]
    if last == 0:
        return 0
    direction = 1 if last > 0 else -1
    streak = 0
    for v in reversed(vals):
        if (v > 0 and direction > 0) or (v < 0 and direction < 0):
            streak += 1
        else:
            break
    return streak * direction


def _determine_signal(foreign_net: float, institution_net: float,
                      individual_net: float,
                      f_streak: int, i_streak: int) -> str:
    both_buy  = foreign_net > 0 and institution_net > 0
    both_sell = foreign_net < 0 and institution_net < 0

    if both_buy and f_streak >= 2 and i_streak >= 2:
        return "쌍끌기 강매수"
    if both_buy:
        return "외국인+기관 동반매수"
    if both_sell:
        return "외국인+기관 동반매도"
    if foreign_net > 0 and f_streak >= 3:
        return "외국인 지속 매수"
    if institution_net > 0 and i_streak >= 3:
        return "기관 지속 매수"
    if foreign_net > 0:
        return "외국인 매수 우위"
    if institution_net > 0:
        return "기관 매수 우위"
    if foreign_net < 0 and f_streak <= -3:
        return "외국인 지속 매도"
    if foreign_net < 0 or institution_net < 0:
        return "기관·외국인 매도 우위"
    return "혼조"


def _calc_score(foreign_net: float, institution_net: float,
                f_streak: int, i_streak: int,
                short_ratio: float, program_net: float) -> float:
    score = 0.0

    # 외국인 (최대 ±40점)
    if foreign_net > 0:
        score += 20.0 + min(f_streak * 4, 20)
    elif foreign_net < 0:
        score -= 20.0 + min(abs(f_streak) * 4, 20)

    # 기관 (최대 ±30점)
    if institution_net > 0:
        score += 15.0 + min(i_streak * 3, 15)
    elif institution_net < 0:
        score -= 15.0 + min(abs(i_streak) * 3, 15)

    # 공매도 페널티 (최대 -20점)
    if short_ratio >= 15:
        score -= 20
    elif short_ratio >= 10:
        score -= 15
    elif short_ratio >= 5:
        score -= 8
    elif short_ratio >= 2:
        score -= 3

    # 프로그램 매매 (최대 ±10점)
    if program_net > 0:
        score += 10
    elif program_net < 0:
        score -= 10

    return round(min(max(score, -100.0), 100.0), 2)


# ── AI 해설 ─────────────────────────────────────────────────────

_SUPPLY_SYSTEM_PROMPT = """당신은 한국 주식시장 수급 흐름 분석 전문가입니다.

[역할]
투자자별(외국인/기관/개인) 순매수·매도 데이터를 해설합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "수급 유입 관찰", "매도 압력 존재", "수급 변화 주목", "변동성 확대 가능성"
4. 각 필드 1~2문장 이내, 한국어만

[출력 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_supply_summary": "수급 현황 1~2문장 (시그널 + 핵심 투자자 흐름)",
  "ai_supply_flow": "자금 흐름 특징 1~2문장 (연속 순매수/도 기간, 규모 특이사항)",
  "ai_supply_risk": "주의사항 1~2문장 (공매도, 개인 과열, 변동성 리스크)"
}"""


def _sanitize(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        text = text.replace(phrase, "")
    return text.strip() or None


def _call_supply_ai(stock_code: str, stock_name: str,
                    metrics: dict, analysis_date: date) -> dict:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return {}

    import openai
    client = openai.OpenAI(api_key=api_key)

    prompt = (
        f"[기준일: {analysis_date}] 종목: {stock_name}({stock_code})\n\n"
        f"수급 시그널: {metrics['supply_signal']}\n"
        f"수급 점수: {metrics['supply_score']:.1f}점 (-100~+100)\n\n"
        f"외국인 순매수(당일): {metrics['foreign_net_buy']:+,.0f}백만원  "
        f"| 5일 누적: {metrics['foreign_net_buy_5d']:+,.0f}백만원  "
        f"| 연속: {metrics['foreign_buy_streak']}일\n"
        f"기관 순매수(당일): {metrics['institution_net_buy']:+,.0f}백만원  "
        f"| 5일 누적: {metrics['institution_net_buy_5d']:+,.0f}백만원  "
        f"| 연속: {metrics['institution_buy_streak']}일\n"
        f"개인 순매수(당일): {metrics['individual_net_buy']:+,.0f}백만원\n"
        f"공매도 비중: {metrics['short_sell_ratio']:.2f}%\n\n"
        "위 수급 데이터를 바탕으로 JSON 형태로 분석을 작성하세요."
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SUPPLY_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=600,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "ai_supply_summary": _sanitize(raw.get("ai_supply_summary")),
            "ai_supply_flow":    _sanitize(raw.get("ai_supply_flow")),
            "ai_supply_risk":    _sanitize(raw.get("ai_supply_risk")),
        }
    except Exception as e:
        logger.error(f"[수급AI] {stock_code} 호출 실패: {e}")
        return {}


# ── DB upsert ───────────────────────────────────────────────────

def _upsert(session, stock_code: str, analysis_date: date,
            metrics: dict, ai: dict) -> None:
    values = dict(
        stock_code=stock_code,
        analysis_date=analysis_date,
        **metrics,
        **ai,
    )
    update_vals = {k: v for k, v in values.items()
                   if k not in ("stock_code", "analysis_date")}
    update_vals["updated_at"] = _sf.now()

    stmt = (
        mysql_insert(SupplyDemandAnalysis)
        .values(**values)
        .on_duplicate_key_update(**update_vals)
    )
    session.execute(stmt)


# ── 단일 종목 분석 ────────────────────────────────────────────────

def analyze_stock_supply_demand(stock_code: str,
                                 analysis_date: Optional[date] = None,
                                 with_ai: bool = True) -> dict:
    """
    단일 종목 수급 분석 실행 및 저장.
    참고용 수급 흐름 분석이며 투자 권유가 아닙니다.
    """
    target_date = analysis_date or date.today()

    # 종목명 조회
    session = get_db_session()
    try:
        from app.models.stock import Stock
        row = session.execute(
            select(Stock.stock_name).where(Stock.stock_code == stock_code)
        ).scalar()
        stock_name = row or stock_code
    finally:
        session.close()

    # 1. 투자자별 순매수 데이터
    df = _fetch_investor_trading(stock_code, target_date, lookback=20)
    if df is None or df.empty:
        return {
            "status":  "no_data",
            "message": f"{stock_code} 투자자별 수급 데이터 없음 (비상장/조회불가)",
        }

    # 2. 지표 계산
    foreign_col     = "foreign"     if "foreign"     in df.columns else None
    institution_col = "institution" if "institution" in df.columns else None
    individual_col  = "individual"  if "individual"  in df.columns else None

    def _last(col):
        return float(df[col].iloc[-1]) / 1_000_000 if col else 0.0  # 원 → 백만원

    def _sum5(col):
        return float(df[col].tail(5).sum()) / 1_000_000 if col else 0.0

    def _streak(col):
        return _calc_streak(df[col] / 1_000_000) if col else 0

    foreign_net     = _last(foreign_col)
    institution_net = _last(institution_col)
    individual_net  = _last(individual_col)
    program_net     = 0.0  # 별도 수집 어려우므로 기본값

    foreign_net_5d     = _sum5(foreign_col)
    institution_net_5d = _sum5(institution_col)

    f_streak = _streak(foreign_col)
    i_streak = _streak(institution_col)

    # 3. 공매도
    short_ratio, short_vol = _fetch_short_sell(stock_code, target_date)

    # 4. 시그널·점수
    signal = _determine_signal(foreign_net, institution_net, individual_net, f_streak, i_streak)
    score  = _calc_score(foreign_net, institution_net, f_streak, i_streak, short_ratio, program_net)

    metrics = {
        "foreign_net_buy":       foreign_net,
        "institution_net_buy":   institution_net,
        "individual_net_buy":    individual_net,
        "program_net_buy":       program_net,
        "foreign_net_buy_5d":    foreign_net_5d,
        "institution_net_buy_5d":institution_net_5d,
        "foreign_buy_streak":    f_streak,
        "institution_buy_streak":i_streak,
        "short_sell_ratio":      short_ratio,
        "short_sell_volume":     short_vol,
        "supply_signal":         signal,
        "supply_score":          score,
    }

    # 5. AI 해설
    ai = _call_supply_ai(stock_code, stock_name, metrics, target_date) if with_ai else {}

    # 6. 저장
    session = get_db_session()
    try:
        _upsert(session, stock_code, target_date, metrics, ai)
        session.commit()
        logger.info(f"[수급분석] {stock_code}({stock_name}) 완료 — {signal} / 점수 {score:.1f}")
        return {
            "status":       "success",
            "stock_code":   stock_code,
            "stock_name":   stock_name,
            "date":         str(target_date),
            **metrics,
            **ai,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"[수급분석] {stock_code} 저장 실패: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


# ── 배치 분석 ─────────────────────────────────────────────────────

def run_supply_demand_batch(analysis_date: Optional[date] = None,
                             limit: int = 80,
                             delay_sec: float = 0.3) -> dict:
    """
    관심종목 + 분석점수 상위 종목 대상으로 수급 분석 배치 실행.
    pykrx 요청 과다 방지를 위해 delay_sec 간격 적용.
    참고용 수급 흐름 분석이며 투자 권유가 아닙니다.
    """
    target_date = analysis_date or date.today()

    # 대상 종목 선정: 관심종목 + 분석점수 상위
    session = get_db_session()
    try:
        from app.models.analysis import StockAnalysisResult
        from app.models.watchlist import WatchlistItem

        # 관심종목
        watchlist_codes = set(
            session.execute(select(WatchlistItem.stock_code)).scalars().all()
        )

        # 분석점수 상위 (당일 기준, bullish_score DESC)
        top_rows = session.execute(
            select(StockAnalysisResult.stock_code)
            .where(StockAnalysisResult.analysis_date == target_date)
            .order_by(StockAnalysisResult.bullish_score.desc())
            .limit(limit)
        ).scalars().all()

        target_codes = list(watchlist_codes | set(top_rows))[:limit]
    finally:
        session.close()

    if not target_codes:
        return {
            "status":  "no_targets",
            "message": f"{target_date} 분석 대상 종목이 없습니다. 분석을 먼저 실행하세요.",
        }

    # 이미 당일 분석된 종목 제외
    session2 = get_db_session()
    try:
        already_done = set(
            session2.execute(
                select(SupplyDemandAnalysis.stock_code)
                .where(SupplyDemandAnalysis.analysis_date == target_date)
            ).scalars().all()
        )
    finally:
        session2.close()

    new_codes = [c for c in target_codes if c not in already_done]
    logger.info(
        f"[수급배치] 시작 — 전체 {len(target_codes)}개 중 신규 {len(new_codes)}개 / {target_date}"
        f" (기존 {len(already_done)}개 스킵)"
    )
    success_cnt = error_cnt = skip_cnt = len(already_done)

    for code in new_codes:
        try:
            result = analyze_stock_supply_demand(code, target_date, with_ai=False)
            if result.get("status") == "success":
                success_cnt += 1
            elif result.get("status") == "no_data":
                skip_cnt += 1
            else:
                error_cnt += 1
        except Exception as e:
            logger.error(f"[수급배치] {code} 오류: {e}")
            error_cnt += 1
        time.sleep(delay_sec)

    logger.info(
        f"[수급배치] 완료 — 성공 {success_cnt} / 스킵 {skip_cnt} / 오류 {error_cnt}"
    )
    return {
        "status":  "success",
        "date":    str(target_date),
        "total":   len(target_codes),
        "success": success_cnt,
        "skipped": skip_cnt,
        "errors":  error_cnt,
        "already_skipped": len(already_done),
    }


# ── 조회 ─────────────────────────────────────────────────────────

def get_supply_demand(stock_code: str,
                      analysis_date: Optional[date] = None) -> Optional[dict]:
    """저장된 수급 분석 결과 조회."""
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        row = session.execute(
            select(SupplyDemandAnalysis)
            .where(
                SupplyDemandAnalysis.stock_code    == stock_code,
                SupplyDemandAnalysis.analysis_date == target_date,
            )
        ).scalar_one_or_none()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_supply_demand_top(signal_filter: Optional[str] = None,
                           analysis_date: Optional[date] = None,
                           limit: int = 20) -> list[dict]:
    """수급 점수 기준 상위 종목 목록 반환."""
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        q = (
            select(SupplyDemandAnalysis)
            .where(SupplyDemandAnalysis.analysis_date == target_date)
            .order_by(SupplyDemandAnalysis.supply_score.desc())
            .limit(limit)
        )
        if signal_filter:
            q = q.where(SupplyDemandAnalysis.supply_signal == signal_filter)
        rows = session.execute(q).scalars().all()
        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()


def _row_to_dict(r: SupplyDemandAnalysis) -> dict:
    return {
        "stock_code":            r.stock_code,
        "analysis_date":         str(r.analysis_date),
        "foreign_net_buy":       float(r.foreign_net_buy       or 0),
        "institution_net_buy":   float(r.institution_net_buy   or 0),
        "individual_net_buy":    float(r.individual_net_buy    or 0),
        "program_net_buy":       float(r.program_net_buy       or 0),
        "foreign_net_buy_5d":    float(r.foreign_net_buy_5d    or 0),
        "institution_net_buy_5d":float(r.institution_net_buy_5d or 0),
        "foreign_buy_streak":    r.foreign_buy_streak    or 0,
        "institution_buy_streak":r.institution_buy_streak or 0,
        "short_sell_ratio":      float(r.short_sell_ratio  or 0),
        "short_sell_volume":     r.short_sell_volume       or 0,
        "supply_signal":         r.supply_signal           or "혼조",
        "supply_score":          float(r.supply_score      or 0),
        "ai_supply_summary":     r.ai_supply_summary,
        "ai_supply_flow":        r.ai_supply_flow,
        "ai_supply_risk":        r.ai_supply_risk,
        "updated_at":            str(r.updated_at)[:16] if r.updated_at else "-",
    }
