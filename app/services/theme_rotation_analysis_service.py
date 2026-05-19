"""
테마 순환 분석 서비스

일별 OHLCV 데이터와 테마 분석 히스토리를 결합하여
시장 내 자금 순환 흐름을 분석합니다.

분석 내용:
  - 오전 강세 테마  : 전일 종가 → 당일 시가 갭 (갭 상승 = 오전 수급 유입)
  - 오후 강세 테마  : 시가 → 종가 등락 (장중 매수세 강도)
  - 장마감 강세 테마 : 종가의 당일 범위 내 위치 (상위 = 마감 강세)
  - 순환매 유입 테마 : 전일 약세 → 당일 반등 전환
  - 이탈 테마       : 전일 강세 → 당일 약화

계산 항목:
  theme_rotation_score / theme_flow_strength / intraday_theme_rank

주의:
  - 투자 추천, 매수/매도 권유 시스템이 아닙니다.
  - 모든 결과는 참고용 시장 흐름 분석 정보입니다.
"""
import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import func as _sf, select, text

from app.config import settings
from app.database import get_db_session
from app.models.price import StockDailyPrice
from app.models.theme_analysis_result import ThemeAnalysisResult
from app.models.theme_rotation_result import ThemeRotationResult, ThemeRotationSummary

logger = logging.getLogger(__name__)

DISCLAIMER = "본 테마 순환 분석은 참고용이며 투자 권유가 아닙니다."
_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

_AI_SYSTEM = """당신은 한국 주식 테마 순환매 흐름 분석 전문가입니다.

[역할]
당일 테마별 장중 흐름 데이터를 기반으로 자금 순환 패턴을 평가하고
시장 참여자가 이해할 수 있는 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장"
3. 허용 표현: "순환매 흐름 관찰", "자금 이동 확인", "테마 부각", "흐름 감지"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_rotation_overview": "당일 순환매 흐름 종합 평가 1~2문장",
  "ai_theme_flow_comment": "테마 자금 이동 특징 및 순환매 체인 묘사 1~2문장"
}"""

_ROTATION_SIGNAL_PRIORITY = [
    "순환매 유입", "유지 강세", "횡보", "이탈", "약세 지속",
]


# ── 테마 매핑 ─────────────────────────────────────────────────────

def _load_theme_map() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "theme_mapping.json"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("themes", {})
    except Exception as e:
        logger.error(f"[테마순환] 매핑 로드 실패: {e}")
        return {}


# ── 가격 데이터 로드 ──────────────────────────────────────────────

def _load_today_prices(session, analysis_date: date) -> dict[str, object]:
    """당일 모든 종목의 OHLCV 로드 → {stock_code: row}."""
    rows = session.execute(
        select(StockDailyPrice)
        .where(StockDailyPrice.trade_date == analysis_date)
        .where(StockDailyPrice.close_price > 0)
    ).scalars().all()
    return {r.stock_code: r for r in rows}


def _load_prev_close_map(session, analysis_date: date) -> dict[str, float]:
    """전일 종가 맵 로드 (analysis_date 직전 거래일)."""
    past_start = analysis_date - timedelta(days=14)
    prev_date = session.execute(
        select(_sf.max(StockDailyPrice.trade_date))
        .where(StockDailyPrice.trade_date >= past_start)
        .where(StockDailyPrice.trade_date < analysis_date)
    ).scalar_one_or_none()

    if not prev_date:
        return {}

    rows = session.execute(
        select(StockDailyPrice.stock_code, StockDailyPrice.close_price)
        .where(StockDailyPrice.trade_date == prev_date)
        .where(StockDailyPrice.close_price > 0)
    ).all()
    return {r.stock_code: float(r.close_price) for r in rows}


def _load_recent_theme_returns(
    session, analysis_date: date, days: int = 5
) -> dict[date, dict[str, float]]:
    """
    최근 N 거래일의 테마별 1일 수익률 로드.

    반환: {trade_date: {theme_name: avg_return_1d}}
    """
    start = analysis_date - timedelta(days=days * 3 + 5)
    rows = session.execute(
        select(
            ThemeAnalysisResult.analysis_date,
            ThemeAnalysisResult.theme_name,
            ThemeAnalysisResult.avg_return_1d,
        )
        .where(ThemeAnalysisResult.analysis_date >= start)
        .where(ThemeAnalysisResult.analysis_date < analysis_date)
        .order_by(ThemeAnalysisResult.analysis_date.desc())
    ).all()

    result: dict[date, dict[str, float]] = {}
    for r in rows:
        d = r.analysis_date
        if d not in result:
            result[d] = {}
        result[d][r.theme_name] = float(r.avg_return_1d or 0.0)
    # 최근 N거래일만 유지
    sorted_dates = sorted(result.keys(), reverse=True)[:days]
    return {d: result[d] for d in sorted_dates}


def _load_prev_rotation_ranks(session, analysis_date: date) -> dict[str, int]:
    """전일 intraday_theme_rank 로드 → {theme_name: rank}."""
    past_start = analysis_date - timedelta(days=10)
    prev_date = session.execute(
        select(_sf.max(ThemeRotationResult.analysis_date))
        .where(ThemeRotationResult.analysis_date >= past_start)
        .where(ThemeRotationResult.analysis_date < analysis_date)
    ).scalar_one_or_none()

    if not prev_date:
        return {}

    rows = session.execute(
        select(ThemeRotationResult.theme_name, ThemeRotationResult.intraday_theme_rank)
        .where(ThemeRotationResult.analysis_date == prev_date)
    ).all()
    return {r.theme_name: r.intraday_theme_rank for r in rows if r.intraday_theme_rank}


# ── 종목별 장중 지표 ──────────────────────────────────────────────

def _stock_intraday_metrics(row, prev_close: Optional[float]) -> Optional[dict]:
    """단일 종목의 오전·오후·마감 지표 계산."""
    o = float(row.open_price  or 0)
    h = float(row.high_price  or 0)
    l = float(row.low_price   or 0)
    c = float(row.close_price or 0)
    tv = float(row.trading_value or 0)

    if o <= 0 or c <= 0 or h < l:
        return None

    # 오전: 갭 (전일 종가 → 시가)
    gap = ((o / prev_close) - 1.0) * 100.0 if prev_close and prev_close > 0 else None

    # 오후: 장중 등락 (시가 → 종가)
    intraday_move = ((c / o) - 1.0) * 100.0

    # 마감: 당일 범위 내 종가 위치 [0, 1]
    day_range = h - l
    close_strength = (c - l) / day_range if day_range > 0 else 0.5

    return {
        "gap":            gap,
        "intraday_move":  intraday_move,
        "close_strength": close_strength,
        "trading_value":  tv,
    }


def _safe_mean(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


# ── 순환 점수 산출 ────────────────────────────────────────────────

def _to_rotation_score(
    intraday: float,
    gap: Optional[float],
    close_str: float,
) -> float:
    """오전·오후·마감 지표 → 순환 점수 (-100 ~ +100)."""
    # 오후 등락: ±5% → ±100
    intra_s = max(-100.0, min(100.0, intraday * 20.0))
    # 갭: ±3% → ±100
    gap_s   = max(-100.0, min(100.0, (gap or 0.0) * 33.33))
    # 마감 위치: [0,1] → [-50, +50]
    close_s = (close_str - 0.5) * 100.0
    return round(intra_s * 0.40 + gap_s * 0.30 + close_s * 0.30, 2)


def _to_flow_strength(
    rotation_score: float,
    tv_rank: int,
    total_themes: int,
) -> float:
    """순환 점수 + 거래대금 순위 → 자금 흐름 강도 (0 ~ 100)."""
    tv_pct = (1.0 - (tv_rank - 1) / max(total_themes, 1)) * 100.0
    return round(abs(rotation_score) * 0.50 + tv_pct * 0.50, 2)


def _detect_rotation_signal(
    theme_name: str,
    today_intraday: float,
    recent_returns: dict[date, dict[str, float]],
) -> str:
    """
    오늘 장중 흐름 + 최근 수익률 이력 → 순환 시그널.

    순환매 유입: 전일 약세 → 오늘 반등
    유지 강세:  전일 강세 → 오늘도 강세
    이탈:       전일 강세 → 오늘 약화
    약세 지속:  전일 약세 → 오늘도 약세
    횡보:       명확한 방향 없음
    """
    dates_sorted = sorted(recent_returns.keys(), reverse=True)
    if not dates_sorted:
        # 이력 없음 → 당일 데이터만으로 판단
        if today_intraday >= 1.0:
            return "유지 강세"
        if today_intraday <= -1.0:
            return "약세 지속"
        return "횡보"

    prev_1d = recent_returns[dates_sorted[0]].get(theme_name)
    prev_2d = recent_returns[dates_sorted[1]].get(theme_name) if len(dates_sorted) >= 2 else None

    if prev_1d is None:
        return "횡보"

    if today_intraday >= 0.5 and prev_1d <= -0.3:
        return "순환매 유입"
    if today_intraday >= 0.5 and prev_1d >= 0.3:
        return "유지 강세"
    if today_intraday <= -0.5 and prev_1d >= 0.3:
        return "이탈"
    if today_intraday <= -0.5 and prev_1d <= -0.3:
        return "약세 지속"

    # 2일 가속도 확인
    if prev_2d is not None:
        accel = prev_1d - prev_2d           # 수익률 변화 방향
        if accel > 0.5 and today_intraday > 0:
            return "순환매 유입"
        if accel < -0.5 and today_intraday < 0:
            return "이탈"

    return "횡보"


def _build_rotation_chain(items_by_intraday: list[dict]) -> str:
    """
    인트라데이 순위 상위 3개 테마로 순환 체인 텍스트 생성.
    예: "AI·빅데이터 → 반도체 → 원전"
    """
    names = [it["theme_name"] for it in items_by_intraday[:3] if it["theme_intraday_score"] > 0]
    return " → ".join(names) if names else ""


# ── AI 해설 ───────────────────────────────────────────────────────

def _sanitize(txt: Optional[str]) -> Optional[str]:
    if not txt:
        return txt
    for p in _BANNED:
        txt = txt.replace(p, "")
    return txt.strip() or None


def _call_rotation_ai(
    rotation_chain: str,
    top_intraday: list[dict],
    rotation_inflow: list[str],
    rotation_outflow: list[str],
    target_date: date,
) -> dict:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return {}
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        def _fmt_list(items: list[dict], key="theme_name", score_key="theme_intraday_score") -> str:
            return ", ".join(
                f"{it[key]}({it.get(score_key, 0):+.2f}%)"
                for it in items[:5]
            )

        prompt = (
            f"[기준일: {target_date}] 테마 순환 분석 결과\n\n"
            f"■ 순환매 체인 (장중 강세 순서)\n  {rotation_chain or '뚜렷한 순환 없음'}\n\n"
            f"■ 장중(오후) 강세 상위 테마\n  {_fmt_list(top_intraday)}\n\n"
            f"■ 순환매 유입 테마\n  {', '.join(rotation_inflow[:5]) or '없음'}\n\n"
            f"■ 이탈 테마\n  {', '.join(rotation_outflow[:5]) or '없음'}\n\n"
            "위 데이터를 바탕으로 JSON 형식의 순환매 흐름 해설을 작성하세요."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=450,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "ai_rotation_overview":  _sanitize(raw.get("ai_rotation_overview")),
            "ai_theme_flow_comment": _sanitize(raw.get("ai_theme_flow_comment")),
        }
    except Exception as e:
        logger.error(f"[테마순환AI] 오류: {e}")
        return {}


# ── DB 저장 ───────────────────────────────────────────────────────

def _upsert_result(session, analysis_date: date, data: dict) -> None:
    _COLS = [
        "theme_name", "stock_count",
        "theme_morning_score", "theme_intraday_score", "theme_close_strength",
        "theme_rotation_score", "theme_flow_strength", "intraday_theme_rank",
        "rotation_signal", "prev_intraday_rank", "rank_change",
        "total_trading_value",
    ]
    set_clause = ", ".join(f"{c} = :{c}" for c in _COLS)
    sql = text(
        f"INSERT INTO theme_rotation_results (analysis_date, {', '.join(_COLS)}) "
        f"VALUES (:analysis_date, {', '.join(f':{c}' for c in _COLS)}) "
        f"ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    params = {"analysis_date": analysis_date}
    for col in _COLS:
        params[col] = data.get(col)
    session.execute(sql, params)


def _upsert_summary(session, analysis_date: date, data: dict) -> None:
    _COLS = [
        "total_themes_analyzed",
        "top_morning_themes", "top_intraday_themes", "top_close_themes",
        "rotation_inflow", "rotation_outflow", "rotation_chain",
        "ai_rotation_overview", "ai_theme_flow_comment",
    ]
    set_clause = ", ".join(f"{c} = :{c}" for c in _COLS)
    sql = text(
        f"INSERT INTO theme_rotation_summary (analysis_date, {', '.join(_COLS)}) "
        f"VALUES (:analysis_date, {', '.join(f':{c}' for c in _COLS)}) "
        f"ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    params = {"analysis_date": analysis_date}
    for col in _COLS:
        params[col] = data.get(col)
    session.execute(sql, params)
    session.commit()


# ── 메인 분석 ────────────────────────────────────────────────────

def run_theme_rotation_analysis(
    analysis_date: Optional[date] = None,
    with_ai: bool = True,
) -> dict:
    """
    당일 테마별 순환 흐름 분석 실행.

    Returns:
        {status, analysis_date, total_themes, rotation_inflow, rotation_outflow, rotation_chain}
    """
    if analysis_date is None:
        analysis_date = date.today()

    session = get_db_session()
    try:
        # ── 1. 데이터 로드 ────────────────────────────────────────
        theme_map     = _load_theme_map()
        if not theme_map:
            return {"status": "error", "message": "테마 매핑 데이터 없음"}

        price_map     = _load_today_prices(session, analysis_date)
        if not price_map:
            return {"status": "no_data", "message": f"{analysis_date} 가격 데이터 없음"}

        prev_close    = _load_prev_close_map(session, analysis_date)
        recent_returns = _load_recent_theme_returns(session, analysis_date)
        prev_ranks    = _load_prev_rotation_ranks(session, analysis_date)

        # ── 2. 테마별 집계 ───────────────────────────────────────
        theme_items: list[dict] = []

        for theme_name, theme_info in theme_map.items():
            codes = [s.get("code", "") for s in theme_info.get("stocks", [])]

            stock_metrics: list[dict] = []
            for code in codes:
                p = price_map.get(code)
                if p is None:
                    continue
                m = _stock_intraday_metrics(p, prev_close.get(code))
                if m:
                    stock_metrics.append(m)

            if not stock_metrics:
                continue

            n = len(stock_metrics)
            avg_gap      = _safe_mean([m["gap"]           for m in stock_metrics])
            avg_intraday = _safe_mean([m["intraday_move"] for m in stock_metrics])
            avg_close    = _safe_mean([m["close_strength"] for m in stock_metrics])
            total_tv     = sum(m["trading_value"] for m in stock_metrics)

            if avg_intraday is None:
                continue
            avg_close = avg_close or 0.5

            rot_score = _to_rotation_score(avg_intraday, avg_gap, avg_close)
            rot_signal = _detect_rotation_signal(theme_name, avg_intraday, recent_returns)

            theme_items.append({
                "theme_name":          theme_name,
                "stock_count":         n,
                "theme_morning_score": round(avg_gap or 0.0, 4),
                "theme_intraday_score": round(avg_intraday, 4),
                "theme_close_strength": round(avg_close, 4),
                "theme_rotation_score": rot_score,
                "rotation_signal":     rot_signal,
                "total_trading_value": int(total_tv),
                # 채워질 필드
                "intraday_theme_rank":  None,
                "theme_flow_strength":  None,
                "prev_intraday_rank":   None,
                "rank_change":          None,
            })

        if not theme_items:
            return {"status": "no_data", "message": "유효한 테마 데이터 없음"}

        total = len(theme_items)

        # ── 3. 인트라데이 순위 부여 ──────────────────────────────
        theme_items.sort(key=lambda x: x["theme_intraday_score"], reverse=True)
        for i, item in enumerate(theme_items, start=1):
            item["intraday_theme_rank"] = i

        # TV 순위 → flow_strength
        tv_sorted = sorted(theme_items, key=lambda x: x["total_trading_value"], reverse=True)
        tv_rank_map = {it["theme_name"]: rank for rank, it in enumerate(tv_sorted, start=1)}

        for item in theme_items:
            tv_r = tv_rank_map[item["theme_name"]]
            item["theme_flow_strength"] = _to_flow_strength(
                item["theme_rotation_score"], tv_r, total
            )

        # ── 4. 전일 순위 대비 ────────────────────────────────────
        for item in theme_items:
            prev_r = prev_ranks.get(item["theme_name"])
            item["prev_intraday_rank"] = prev_r
            if prev_r and item["intraday_theme_rank"]:
                item["rank_change"] = prev_r - item["intraday_theme_rank"]  # 양수=상승

        # ── 5. DB 저장 (per-theme) ────────────────────────────────
        for item in theme_items:
            _upsert_result(session, analysis_date, item)
        session.commit()

        # ── 6. 요약 생성 ─────────────────────────────────────────
        # 각 시간대별 상위 (score 기준)
        by_morning  = sorted(theme_items, key=lambda x: x["theme_morning_score"],  reverse=True)
        by_intraday = sorted(theme_items, key=lambda x: x["theme_intraday_score"], reverse=True)
        by_close    = sorted(theme_items, key=lambda x: x["theme_close_strength"], reverse=True)

        def _brief(item: dict) -> dict:
            return {
                "theme_name":           item["theme_name"],
                "theme_morning_score":  item["theme_morning_score"],
                "theme_intraday_score": item["theme_intraday_score"],
                "theme_close_strength": item["theme_close_strength"],
                "theme_rotation_score": item["theme_rotation_score"],
                "theme_flow_strength":  item["theme_flow_strength"],
                "intraday_theme_rank":  item["intraday_theme_rank"],
                "rotation_signal":      item["rotation_signal"],
                "rank_change":          item["rank_change"],
            }

        inflow_themes  = [it["theme_name"] for it in theme_items if it["rotation_signal"] == "순환매 유입"]
        outflow_themes = [it["theme_name"] for it in theme_items if it["rotation_signal"] == "이탈"]

        # 순환매 체인: 장중 강세 상위 + 유입 신호 테마 결합
        chain_candidates = [it for it in by_intraday if it["theme_intraday_score"] > 0]
        rotation_chain   = _build_rotation_chain(chain_candidates)

        summary_data: dict = {
            "total_themes_analyzed": total,
            "top_morning_themes":   json.dumps([_brief(x) for x in by_morning[:5]],  ensure_ascii=False),
            "top_intraday_themes":  json.dumps([_brief(x) for x in by_intraday[:5]], ensure_ascii=False),
            "top_close_themes":     json.dumps([_brief(x) for x in by_close[:5]],    ensure_ascii=False),
            "rotation_inflow":      json.dumps(inflow_themes,  ensure_ascii=False),
            "rotation_outflow":     json.dumps(outflow_themes, ensure_ascii=False),
            "rotation_chain":       rotation_chain,
        }

        # ── 7. AI 해설 ───────────────────────────────────────────
        if with_ai:
            ai = _call_rotation_ai(
                rotation_chain,
                [_brief(x) for x in by_intraday[:5]],
                inflow_themes,
                outflow_themes,
                analysis_date,
            )
            summary_data.update(ai)

        _upsert_summary(session, analysis_date, summary_data)

        logger.info(
            f"[테마순환] {analysis_date} 분석 완료 "
            f"테마={total} 유입={len(inflow_themes)} 이탈={len(outflow_themes)} "
            f"체인='{rotation_chain}'"
        )
        return {
            "status": "success",
            "analysis_date":    str(analysis_date),
            "total_themes":     total,
            "rotation_inflow":  inflow_themes,
            "rotation_outflow": outflow_themes,
            "rotation_chain":   rotation_chain,
        }

    except Exception as e:
        logger.error(f"[테마순환] {analysis_date} 분석 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


# ── DB 읽기 ───────────────────────────────────────────────────────

def _result_to_dict(row: ThemeRotationResult) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    return {
        "analysis_date":        str(row.analysis_date),
        "theme_name":           row.theme_name,
        "stock_count":          row.stock_count,
        "theme_morning_score":  _f(row.theme_morning_score),
        "theme_intraday_score": _f(row.theme_intraday_score),
        "theme_close_strength": _f(row.theme_close_strength),
        "theme_rotation_score": _f(row.theme_rotation_score),
        "theme_flow_strength":  _f(row.theme_flow_strength),
        "intraday_theme_rank":  row.intraday_theme_rank,
        "rotation_signal":      row.rotation_signal or "횡보",
        "prev_intraday_rank":   row.prev_intraday_rank,
        "rank_change":          row.rank_change,
        "total_trading_value":  row.total_trading_value,
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def _summary_to_dict(row: ThemeRotationSummary) -> dict:
    def _json(v):
        try:
            return json.loads(v) if v else []
        except Exception:
            return []

    return {
        "analysis_date":         str(row.analysis_date),
        "total_themes_analyzed": row.total_themes_analyzed,
        "top_morning_themes":    _json(row.top_morning_themes),
        "top_intraday_themes":   _json(row.top_intraday_themes),
        "top_close_themes":      _json(row.top_close_themes),
        "rotation_inflow":       _json(row.rotation_inflow),
        "rotation_outflow":      _json(row.rotation_outflow),
        "rotation_chain":        row.rotation_chain or "",
        "ai_rotation_overview":  row.ai_rotation_overview,
        "ai_theme_flow_comment": row.ai_theme_flow_comment,
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def get_theme_rotation_summary(analysis_date: Optional[date] = None) -> Optional[dict]:
    """당일 순환 요약 조회."""
    session = get_db_session()
    try:
        q = select(ThemeRotationSummary)
        if analysis_date:
            q = q.where(ThemeRotationSummary.analysis_date == analysis_date)
        q = q.order_by(ThemeRotationSummary.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _summary_to_dict(row) if row else None
    finally:
        session.close()


def get_theme_rotation_results(
    analysis_date: Optional[date] = None,
    signal: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """테마별 순환 결과 목록 조회."""
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(ThemeRotationResult.analysis_date)
                .order_by(ThemeRotationResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(ThemeRotationResult).where(ThemeRotationResult.analysis_date == analysis_date)
        if signal:
            q = q.where(ThemeRotationResult.rotation_signal == signal)
        q = q.order_by(ThemeRotationResult.intraday_theme_rank.asc()).limit(limit)
        return [_result_to_dict(r) for r in session.execute(q).scalars().all()]
    finally:
        session.close()
