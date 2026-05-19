"""
시장 주도주 분석 서비스

stock_daily_prices · stock_analysis_results · theme_analysis_results를
결합하여 당일 시장을 실질적으로 주도하는 종목을 탐지합니다.

분석 기준:
  - 거래대금 증가율 (5일 평균 대비, 30%)
  - 시가총액 영향력 (순위 기반, 20%)
  - 상대강도 (vs KOSPI/KOSDAQ, 25%)
  - 거래량 비율 (15%)
  - 테마 영향력 (소속 테마 시그널, 10%)

계산 항목:
  market_leader_score / market_influence_score
  trading_value_rank / theme_influence_score
  leader_signal (시장 주도주 / 주도 후보 / 관심 종목 / 일반)

주의:
  - 투자 추천, 매수/매도 권유 시스템이 아닙니다.
  - 모든 결과는 참고용 시장 흐름 분석 정보입니다.
"""
import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func as _sf, select, text

from app.config import settings
from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.market_leader_result import MarketLeaderResult, MarketLeaderSummary
from app.models.price import StockDailyPrice
from app.models.stock import Stock
from app.models.theme_analysis_result import ThemeAnalysisResult

logger = logging.getLogger(__name__)

DISCLAIMER = "본 시장 주도주 분석은 참고용이며 투자 권유가 아닙니다."
_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

_AI_SYSTEM = """당신은 한국 주식 시장 주도주 흐름 분석 전문가입니다.

[역할]
당일 시장 거래 데이터와 종목 지표를 바탕으로 시장을 주도하는 흐름을 평가하고
시장 참여자가 이해할 수 있는 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "주도 흐름 관찰", "자금 집중", "테마 부각", "흐름 확인"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_market_summary": "당일 시장 주도 흐름 종합 평가 1~2문장",
  "ai_theme_flow": "거래대금 집중 테마 및 자금 흐름 특징 1~2문장",
  "ai_leader_comment": "주요 시장 주도주 특징 해설 1~2문장"
}"""

_THEME_SIGNAL_SCORE: dict[str, float] = {
    "매우 강세":   100.0,
    "강세 흐름":    75.0,
    "순환매 관심":  50.0,
    "혼조":         25.0,
    "약세 흐름":    10.0,
    "하락 주의":     0.0,
}


# ── 데이터 로드 ───────────────────────────────────────────────────

def _load_today_prices(session, analysis_date: date, limit: int) -> list:
    """당일 거래대금 상위 종목 가격 데이터 로드."""
    return session.execute(
        select(StockDailyPrice)
        .where(StockDailyPrice.trade_date == analysis_date)
        .where(StockDailyPrice.trading_value > 0)
        .order_by(StockDailyPrice.trading_value.desc())
        .limit(limit)
    ).scalars().all()


def _load_avg_trading_value(session, analysis_date: date) -> dict[str, float]:
    """과거 5 거래일 평균 거래대금 계산 (stock_code → avg_tv)."""
    past_start = analysis_date - timedelta(days=14)
    rows = session.execute(
        select(StockDailyPrice.stock_code, StockDailyPrice.trading_value, StockDailyPrice.trade_date)
        .where(StockDailyPrice.trade_date >= past_start)
        .where(StockDailyPrice.trade_date < analysis_date)
        .where(StockDailyPrice.trading_value > 0)
        .order_by(StockDailyPrice.trade_date.desc())
    ).all()
    tv_history: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        tv_history[r.stock_code].append(float(r.trading_value))
    return {
        code: sum(vals[:5]) / min(len(vals), 5)
        for code, vals in tv_history.items()
        if vals
    }


def _load_analysis_results(session, analysis_date: date) -> dict[str, StockAnalysisResult]:
    """당일 분석 결과 로드 (중복 시 최신 행 우선)."""
    rows = session.execute(
        select(StockAnalysisResult)
        .where(StockAnalysisResult.analysis_date == analysis_date)
        .order_by(StockAnalysisResult.id.desc())
    ).scalars().all()
    result: dict[str, StockAnalysisResult] = {}
    for r in rows:
        if r.stock_code not in result:
            result[r.stock_code] = r
    return result


def _load_stock_info(session) -> dict[str, Stock]:
    rows = session.execute(select(Stock).where(Stock.is_active == 1)).scalars().all()
    return {s.stock_code: s for s in rows}


def _load_theme_signals(session, analysis_date: date) -> dict[str, str]:
    """테마별 당일 시그널 로드."""
    rows = session.execute(
        select(ThemeAnalysisResult.theme_name, ThemeAnalysisResult.theme_signal)
        .where(ThemeAnalysisResult.analysis_date == analysis_date)
    ).all()
    return {r.theme_name: (r.theme_signal or "") for r in rows}


def _build_code_theme_map() -> dict[str, str]:
    """stock_code → theme_name (data/theme_mapping.json 기반)."""
    from pathlib import Path
    mapping_path = Path(__file__).parent.parent.parent / "data" / "theme_mapping.json"
    try:
        with open(mapping_path, encoding="utf-8") as f:
            data = json.load(f)
        result: dict[str, str] = {}
        for theme_name, info in data.get("themes", {}).items():
            for s in info.get("stocks", []):
                code = s.get("code", "")
                if code and code not in result:
                    result[code] = theme_name
        return result
    except Exception as e:
        logger.warning(f"[주도주] 테마 매핑 로드 실패: {e}")
        return {}


# ── 점수 계산 ─────────────────────────────────────────────────────

def _trading_value_score(tv_rank: int, total: int) -> float:
    """거래대금 순위 → 점수 (순위 백분위 기반, 0-100)."""
    if total <= 0:
        return 0.0
    percentile = 1.0 - (tv_rank - 1) / total  # 1위 → 1.0, 꼴찌 → 0.0
    return round(percentile * 100, 2)


def _market_influence_score(mc_rank: int, total: int) -> float:
    """시가총액 순위 → 시장 영향력 점수 (비선형 — 상위 집중 강조)."""
    if total <= 0:
        return 0.0
    pct = (mc_rank - 1) / total  # 0 = 최상위, 1 = 최하위
    # 상위 10% 이내: 높은 점수; 이후 급격 감소
    if pct <= 0.05:   return 100.0
    if pct <= 0.10:   return 85.0
    if pct <= 0.20:   return 65.0
    if pct <= 0.35:   return 45.0
    if pct <= 0.50:   return 30.0
    if pct <= 0.70:   return 15.0
    return 5.0


def _relative_strength_to_score(rs: Optional[float]) -> float:
    """상대강도 (비율) → 점수 (0-100)."""
    if rs is None:
        return 50.0
    if rs >= 1.30:   return 100.0
    if rs >= 1.15:   return 85.0
    if rs >= 1.05:   return 70.0
    if rs >= 1.00:   return 55.0
    if rs >= 0.95:   return 35.0
    if rs >= 0.85:   return 15.0
    return 0.0


def _volume_score_from_ratio(ratio: Optional[float]) -> float:
    """20일 거래량 비율 → 점수 (0-100)."""
    if ratio is None:
        return 0.0
    if ratio >= 4.0:   return 100.0
    if ratio >= 3.0:   return 85.0
    if ratio >= 2.0:   return 65.0
    if ratio >= 1.5:   return 45.0
    if ratio >= 1.2:   return 25.0
    if ratio >= 1.0:   return 10.0
    return 0.0


def _calc_market_leader_score(
    tv_score: float,
    rs_score: float,
    mi_score: float,
    vol_score: float,
    theme_score: float,
) -> float:
    return round(
        tv_score   * 0.30
        + rs_score * 0.25
        + mi_score * 0.20
        + vol_score * 0.15
        + theme_score * 0.10,
        2,
    )


def _determine_leader_signal(score: float) -> str:
    if score >= 70:   return "시장 주도주"
    if score >= 50:   return "주도 후보"
    if score >= 30:   return "관심 종목"
    return "일반"


# ── 메인 배치 분석 ────────────────────────────────────────────────

def run_market_leader_analysis(
    analysis_date: Optional[date] = None,
    limit: int = 500,
    with_ai: bool = True,
) -> dict:
    """
    당일 전체 종목 대상 시장 주도주 분석 실행.

    Returns:
        {status, analysis_date, total, leader_count, top_leaders}
    """
    if analysis_date is None:
        analysis_date = date.today()

    session = get_db_session()
    try:
        # ── 1. 데이터 로드 ────────────────────────────────────────
        today_prices   = _load_today_prices(session, analysis_date, limit)
        if not today_prices:
            return {"status": "no_data", "message": f"{analysis_date} 가격 데이터 없음"}

        avg_tv_map     = _load_avg_trading_value(session, analysis_date)
        analysis_map   = _load_analysis_results(session, analysis_date)
        stock_map      = _load_stock_info(session)
        theme_sig_map  = _load_theme_signals(session, analysis_date)
        code_theme_map = _build_code_theme_map()

        # ── 2. 종목별 원시 지표 수집 ─────────────────────────────
        items: list[dict] = []
        for p in today_prices:
            code = p.stock_code
            stock = stock_map.get(code)
            ar    = analysis_map.get(code)

            tv      = float(p.trading_value or 0)
            mc      = float(p.market_cap or 0)
            avg_tv  = avg_tv_map.get(code, 0)
            tv_chg  = round((tv - avg_tv) / avg_tv * 100, 2) if avg_tv > 0 else None

            theme_name   = code_theme_map.get(code)
            theme_signal = theme_sig_map.get(theme_name, "") if theme_name else ""
            theme_score  = _THEME_SIGNAL_SCORE.get(theme_signal, 15.0)  # 테마 없음 = 15

            rs   = float(ar.relative_strength or 1.0) if ar else None
            vr20 = float(ar.volume_ratio_20d  or 0.0) if ar else None
            vs   = float(ar.volume_score      or 0.0) if ar else None

            items.append({
                "stock_code":    code,
                "stock_name":    stock.stock_name if stock else code,
                "market":        stock.market     if stock else "",
                "sector":        stock.sector     if stock else "",
                "trading_value": int(tv),
                "trading_value_vs_avg5": tv_chg,
                "market_cap":    int(mc) if mc else None,
                "relative_strength":       rs,
                "relative_strength_score": _relative_strength_to_score(rs),
                "volume_ratio_20d":  vr20,
                "volume_score":      vs if vs is not None else _volume_score_from_ratio(vr20),
                "theme_name":         theme_name,
                "theme_signal":       theme_signal or None,
                "theme_influence_score": theme_score,
                # 아래 필드는 랭킹 부여 후 채워짐
                "trading_value_rank":   None,
                "market_cap_rank":      None,
                "market_influence_score": None,
                "market_leader_score":  None,
                "leader_signal":        None,
            })

        total = len(items)

        # ── 3. 거래대금·시가총액 순위 부여 ───────────────────────
        items.sort(key=lambda x: x["trading_value"], reverse=True)
        for i, item in enumerate(items, start=1):
            item["trading_value_rank"] = i

        mc_sorted = sorted(items, key=lambda x: x["market_cap"] or 0, reverse=True)
        mc_rank_map: dict[str, int] = {it["stock_code"]: rank for rank, it in enumerate(mc_sorted, start=1)}
        for item in items:
            item["market_cap_rank"] = mc_rank_map[item["stock_code"]]

        # ── 4. 점수 확정 ─────────────────────────────────────────
        for item in items:
            tv_sc = _trading_value_score(item["trading_value_rank"], total)
            mi_sc = _market_influence_score(item["market_cap_rank"], total)
            item["market_influence_score"] = round(mi_sc, 2)

            score = _calc_market_leader_score(
                tv_score    = tv_sc,
                rs_score    = item["relative_strength_score"],
                mi_score    = mi_sc,
                vol_score   = item["volume_score"] or 0.0,
                theme_score = item["theme_influence_score"],
            )
            item["market_leader_score"] = score
            item["leader_signal"]       = _determine_leader_signal(score)

        # ── 5. DB 저장 (per-stock) ────────────────────────────────
        _bulk_upsert_leaders(session, analysis_date, items)

        # ── 6. 요약 생성 ─────────────────────────────────────────
        items_by_score = sorted(items, key=lambda x: x["market_leader_score"], reverse=True)
        items_by_tv    = sorted(items, key=lambda x: x["trading_value"],       reverse=True)
        items_by_mi    = sorted(items, key=lambda x: x["market_influence_score"] or 0, reverse=True)

        def _brief(it: dict) -> dict:
            return {
                "stock_code":          it["stock_code"],
                "stock_name":          it["stock_name"],
                "market":              it["market"],
                "sector":              it["sector"],
                "market_leader_score": it["market_leader_score"],
                "leader_signal":       it["leader_signal"],
                "trading_value":       it["trading_value"],
                "trading_value_vs_avg5": it["trading_value_vs_avg5"],
                "market_influence_score": it["market_influence_score"],
                "theme_name":          it["theme_name"],
                "theme_signal":        it["theme_signal"],
            }

        top_leaders       = [_brief(x) for x in items_by_score[:10]]
        top_trading_value = [_brief(x) for x in items_by_tv[:10]]
        top_market_inf    = [_brief(x) for x in items_by_mi[:5]]

        leader_items      = [x for x in items if x["leader_signal"] == "시장 주도주"]
        leader_count      = len(leader_items)
        kospi_leaders     = sum(1 for x in leader_items if x["market"] == "KOSPI")
        kosdaq_leaders    = sum(1 for x in leader_items if x["market"] == "KOSDAQ")

        # 주도 테마: theme_influence_score 상위 (거래대금 가중 집계)
        theme_tv: dict[str, float] = defaultdict(float)
        for it in items:
            if it["theme_name"]:
                theme_tv[it["theme_name"]] += it["trading_value"]
        dominant_themes = [t for t, _ in sorted(theme_tv.items(), key=lambda x: x[1], reverse=True)[:5]]

        summary: dict = {
            "total_analyzed":      total,
            "leader_count":        leader_count,
            "kospi_leader_count":  kospi_leaders,
            "kosdaq_leader_count": kosdaq_leaders,
            "top_leaders":         json.dumps(top_leaders,       ensure_ascii=False),
            "top_trading_value":   json.dumps(top_trading_value, ensure_ascii=False),
            "top_market_influence": json.dumps(top_market_inf,   ensure_ascii=False),
            "dominant_themes":     json.dumps(dominant_themes,   ensure_ascii=False),
        }

        # ── 7. AI 해설 ───────────────────────────────────────────
        if with_ai:
            ai = _call_market_leader_ai(top_leaders, dominant_themes, analysis_date)
            summary.update(ai)

        _upsert_summary(session, analysis_date, summary)

        logger.info(
            f"[시장주도주] {analysis_date} 분석 완료 "
            f"총={total} 주도주={leader_count} "
            f"KOSPI={kospi_leaders} KOSDAQ={kosdaq_leaders}"
        )
        return {
            "status": "success",
            "analysis_date": str(analysis_date),
            "total": total,
            "leader_count": leader_count,
            "top_leaders": top_leaders,
            "dominant_themes": dominant_themes,
        }

    except Exception as e:
        logger.error(f"[시장주도주] {analysis_date} 분석 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


# ── DB 저장 ───────────────────────────────────────────────────────

def _bulk_upsert_leaders(session, analysis_date: date, items: list[dict]) -> None:
    """market_leader_results 일괄 upsert."""
    _COLS = [
        "stock_name", "market", "sector",
        "trading_value", "trading_value_rank", "trading_value_vs_avg5",
        "market_cap", "market_cap_rank", "market_influence_score",
        "relative_strength", "relative_strength_score",
        "volume_ratio_20d", "volume_score",
        "theme_name", "theme_signal", "theme_influence_score",
        "market_leader_score", "leader_signal",
    ]
    set_clause = ", ".join(f"{c} = :{c}" for c in _COLS)
    sql = text(
        f"INSERT INTO market_leader_results (stock_code, analysis_date, {', '.join(_COLS)}) "
        f"VALUES (:stock_code, :analysis_date, {', '.join(f':{c}' for c in _COLS)}) "
        f"ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    for item in items:
        params = {"stock_code": item["stock_code"], "analysis_date": analysis_date}
        for col in _COLS:
            params[col] = item.get(col)
        session.execute(sql, params)
    session.commit()


def _upsert_summary(session, analysis_date: date, data: dict) -> None:
    """market_leader_summary upsert."""
    fields = {k: v for k, v in data.items()}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(
        "INSERT INTO market_leader_summary (analysis_date, "
        + ", ".join(fields.keys())
        + ") VALUES (:analysis_date, "
        + ", ".join(f":{k}" for k in fields)
        + f") ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    session.execute(sql, {"analysis_date": analysis_date, **fields})
    session.commit()


# ── AI 해설 ───────────────────────────────────────────────────────

def _sanitize(txt: Optional[str]) -> Optional[str]:
    if not txt:
        return txt
    for p in _BANNED:
        txt = txt.replace(p, "")
    return txt.strip() or None


def _call_market_leader_ai(
    top_leaders: list[dict],
    dominant_themes: list[str],
    target_date: date,
) -> dict:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return {}
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        def _tv_str(tv: int) -> str:
            return f"{tv / 1_000_000_000_000:.2f}조원" if tv >= 1_000_000_000_000 else f"{tv / 1_000_000_000:.1f}십억원"

        leaders_text = "\n".join(
            f"  {i+1}. {it['stock_name']}({it['stock_code']}) "
            f"[{it['market']}·{it.get('sector','') or ''}] "
            f"점수={it['market_leader_score']:.1f} "
            f"거래대금={_tv_str(it['trading_value'])} "
            f"테마={it.get('theme_name') or 'N/A'}"
            for i, it in enumerate(top_leaders[:5])
        )

        prompt = (
            f"[기준일: {target_date}] 시장 주도주 분석 결과\n\n"
            f"■ 시장 주도 점수 상위 5종목\n{leaders_text}\n\n"
            f"■ 주도 테마 (거래대금 집중 순)\n"
            + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(dominant_themes[:5]))
            + "\n\n위 데이터를 바탕으로 JSON 형식의 시장 주도 흐름 해설을 작성하세요."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "ai_market_summary": _sanitize(raw.get("ai_market_summary")),
            "ai_theme_flow":     _sanitize(raw.get("ai_theme_flow")),
            "ai_leader_comment": _sanitize(raw.get("ai_leader_comment")),
        }
    except Exception as e:
        logger.error(f"[시장주도주AI] 오류: {e}")
        return {}


# ── DB 읽기 ───────────────────────────────────────────────────────

def _result_to_dict(row: MarketLeaderResult) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    return {
        "stock_code":    row.stock_code,
        "analysis_date": str(row.analysis_date),
        "stock_name":    row.stock_name,
        "market":        row.market,
        "sector":        row.sector,
        "trading_value":          row.trading_value,
        "trading_value_rank":     row.trading_value_rank,
        "trading_value_vs_avg5":  _f(row.trading_value_vs_avg5),
        "market_cap":             row.market_cap,
        "market_cap_rank":        row.market_cap_rank,
        "market_influence_score": _f(row.market_influence_score),
        "relative_strength":      _f(row.relative_strength),
        "relative_strength_score": _f(row.relative_strength_score),
        "volume_ratio_20d":       _f(row.volume_ratio_20d),
        "volume_score":           _f(row.volume_score),
        "theme_name":             row.theme_name,
        "theme_signal":           row.theme_signal,
        "theme_influence_score":  _f(row.theme_influence_score),
        "market_leader_score":    _f(row.market_leader_score),
        "leader_signal":          row.leader_signal or "일반",
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def _summary_to_dict(row: MarketLeaderSummary) -> dict:
    def _json(v):
        try:
            return json.loads(v) if v else []
        except Exception:
            return []

    return {
        "analysis_date":      str(row.analysis_date),
        "total_analyzed":     row.total_analyzed,
        "leader_count":       row.leader_count,
        "kospi_leader_count":  row.kospi_leader_count,
        "kosdaq_leader_count": row.kosdaq_leader_count,
        "top_leaders":          _json(row.top_leaders),
        "top_trading_value":    _json(row.top_trading_value),
        "top_market_influence": _json(row.top_market_influence),
        "dominant_themes":      _json(row.dominant_themes),
        "ai_market_summary":   row.ai_market_summary,
        "ai_theme_flow":       row.ai_theme_flow,
        "ai_leader_comment":   row.ai_leader_comment,
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def get_market_leaders(
    analysis_date: Optional[date] = None,
    limit: int = 50,
    signal: Optional[str] = None,
    market: Optional[str] = None,
) -> list[dict]:
    """시장 주도주 목록 조회."""
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(MarketLeaderResult.analysis_date)
                .order_by(MarketLeaderResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(MarketLeaderResult).where(MarketLeaderResult.analysis_date == analysis_date)
        if signal:
            q = q.where(MarketLeaderResult.leader_signal == signal)
        if market:
            q = q.where(MarketLeaderResult.market == market)
        q = q.order_by(MarketLeaderResult.market_leader_score.desc()).limit(limit)
        return [_result_to_dict(r) for r in session.execute(q).scalars().all()]
    finally:
        session.close()


def get_market_leaders_by_trading_value(
    analysis_date: Optional[date] = None,
    limit: int = 30,
    market: Optional[str] = None,
) -> list[dict]:
    """거래대금 상위 종목 조회."""
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(MarketLeaderResult.analysis_date)
                .order_by(MarketLeaderResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(MarketLeaderResult).where(MarketLeaderResult.analysis_date == analysis_date)
        if market:
            q = q.where(MarketLeaderResult.market == market)
        q = q.order_by(MarketLeaderResult.trading_value_rank.asc()).limit(limit)
        return [_result_to_dict(r) for r in session.execute(q).scalars().all()]
    finally:
        session.close()


def get_market_summary(analysis_date: Optional[date] = None) -> Optional[dict]:
    """시장 주도주 일별 요약 조회."""
    session = get_db_session()
    try:
        q = select(MarketLeaderSummary)
        if analysis_date:
            q = q.where(MarketLeaderSummary.analysis_date == analysis_date)
        q = q.order_by(MarketLeaderSummary.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _summary_to_dict(row) if row else None
    finally:
        session.close()
