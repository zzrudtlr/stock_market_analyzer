"""
차트 패턴 분석 서비스

DB 가격 데이터(stock_daily_prices)를 기반으로 기술적 패턴을 탐지합니다.

탐지 패턴:
  - 박스권 돌파 (Box Range Breakout)
  - 신고가 근접 (Near 52-Week High)
  - 거래량 동반 상승 (Volume Breakout)
  - MA20 돌파 (MA20 Breakout)
  - MA60 돌파 (MA60 Breakout)
  - 골든크로스 (Golden Cross)
  - 데드크로스 (Dead Cross)
  - 눌림목 패턴 (Pullback Pattern)

계산 항목:
  breakout_signal / new_high_signal / volume_breakout_signal
  ma20_breakout_signal / ma60_breakout_signal
  golden_cross_signal / dead_cross_signal / pullback_signal
  pattern_score (-100 ~ +100) / chart_signal

주의:
  - 투자 추천, 매수/매도 권유 시스템이 아닙니다.
  - 모든 결과는 참고용 차트 패턴 분석 정보입니다.
"""
import json
import logging
import time
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, text

from app.config import settings
from app.database import get_db_session
from app.models.chart_pattern_analysis_result import ChartPatternAnalysisResult
from app.models.price import StockDailyPrice
from app.models.stock import Stock

logger = logging.getLogger(__name__)

DISCLAIMER = "본 차트 패턴 분석은 참고용이며 투자 권유가 아닙니다."
_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

_AI_SYSTEM = """당신은 한국 주식 기술적 차트 패턴 분석 전문가입니다.

[역할]
차트 패턴 데이터를 기반으로 기술적 흐름을 평가하고
시장 참여자가 이해할 수 있는 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "패턴 관찰", "흐름 확인", "주의 필요", "변동성 존재"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_chart_summary": "차트 패턴 종합 평가 1~2문장",
  "ai_pattern_comment": "탐지된 주요 패턴 설명 1~2문장",
  "ai_trend_comment": "이동평균·추세 흐름 해설 1~2문장"
}"""


# ── 가격 데이터 로드 ──────────────────────────────────────────────

def _load_prices(session, stock_code: str, analysis_date: date, lookback: int = 260) -> Optional[list[dict]]:
    """DB에서 가격 데이터 로드 (오름차순)."""
    start = analysis_date - timedelta(days=lookback * 2)
    rows = session.execute(
        select(StockDailyPrice)
        .where(
            StockDailyPrice.stock_code == stock_code,
            StockDailyPrice.trade_date >= start,
            StockDailyPrice.trade_date <= analysis_date,
        )
        .order_by(StockDailyPrice.trade_date.asc())
    ).scalars().all()
    if not rows:
        return None
    return [
        {
            "close":  float(r.close_price or 0),
            "high":   float(r.high_price or 0),
            "low":    float(r.low_price or 0),
            "volume": float(r.volume or 0),
        }
        for r in rows
        if r.close_price and r.close_price > 0
    ]


def _ma(values: list[float], n: int) -> Optional[float]:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


# ── 패턴 탐지 ─────────────────────────────────────────────────────

def _detect_box_breakout(closes: list[float]) -> tuple[bool, str]:
    """박스권 돌파: 직전 15~60일 박스권 상단을 당일 종가가 돌파."""
    if len(closes) < 25:
        return False, ""
    # 최근 5일 제외, 최대 60일을 박스 구간으로 사용
    box = closes[-61:-5]
    if len(box) < 15:
        return False, ""
    box_high = max(box)
    box_low  = min(box)
    if box_low <= 0:
        return False, ""
    box_range = (box_high - box_low) / box_low
    # 박스권: 변동폭 20% 이내 (좁은 횡보 구간)
    if box_range > 0.20:
        return False, ""
    today = closes[-1]
    prev  = closes[-2]
    if prev <= box_high * 1.005 and today > box_high * 1.01:
        return True, "장기 박스권 상단 돌파 시도가 관찰됩니다."
    return False, ""


def _detect_new_high(closes: list[float]) -> tuple[bool, str]:
    """신고가 근접: 52주 고점(최대 250거래일) 대비 97% 이상."""
    if len(closes) < 20:
        return False, ""
    today    = closes[-1]
    hist     = closes[-251:-1]
    if not hist:
        return False, ""
    high_52w = max(hist)
    if high_52w <= 0:
        return False, ""
    ratio = today / high_52w
    if ratio >= 1.0:
        return True, "52주 신고가 경신 흐름이 관찰됩니다."
    if ratio >= 0.97:
        return True, "52주 신고가에 근접한 흐름이 나타나고 있습니다."
    return False, ""


def _detect_volume_breakout(closes: list[float], volumes: list[float]) -> tuple[bool, str]:
    """거래량 동반 상승: 상승 마감 + 당일 거래량이 20일 평균의 1.5배 이상."""
    if len(closes) < 22 or len(volumes) < 22:
        return False, ""
    today_close = closes[-1]
    prev_close  = closes[-2]
    today_vol   = volumes[-1]
    avg_vol_20  = sum(volumes[-21:-1]) / 20
    if avg_vol_20 <= 0:
        return False, ""
    if today_close > prev_close and today_vol / avg_vol_20 >= 1.5:
        return True, "거래량 동반 상승 흐름이 나타나고 있습니다."
    return False, ""


def _detect_ma20_breakout(closes: list[float]) -> tuple[bool, str]:
    """MA20 돌파: 전일 MA20 하회 → 당일 MA20 상향 돌파."""
    if len(closes) < 22:
        return False, ""
    ma20_today = _ma(closes, 20)
    ma20_prev  = _ma(closes[:-1], 20)
    if ma20_today is None or ma20_prev is None:
        return False, ""
    if closes[-2] < ma20_prev and closes[-1] >= ma20_today:
        return True, "단기 이동평균선(MA20) 상향 돌파 흐름이 확인됩니다."
    return False, ""


def _detect_ma60_breakout(closes: list[float]) -> tuple[bool, str]:
    """MA60 돌파: 전일 MA60 하회 → 당일 MA60 상향 돌파."""
    if len(closes) < 62:
        return False, ""
    ma60_today = _ma(closes, 60)
    ma60_prev  = _ma(closes[:-1], 60)
    if ma60_today is None or ma60_prev is None:
        return False, ""
    if closes[-2] < ma60_prev and closes[-1] >= ma60_today:
        return True, "중기 이동평균선(MA60) 상향 돌파 흐름이 확인됩니다."
    return False, ""


def _detect_golden_cross(closes: list[float]) -> tuple[bool, str]:
    """
    골든크로스 탐지 (두 단계):
      1순위) MA20이 MA60을 상향 돌파 (전일 MA20<MA60, 당일 MA20>=MA60)
      2순위) MA5가 MA20을 상향 돌파
    """
    if len(closes) >= 62:
        ma20_t = _ma(closes, 20)
        ma60_t = _ma(closes, 60)
        ma20_p = _ma(closes[:-1], 20)
        ma60_p = _ma(closes[:-1], 60)
        if None not in (ma20_t, ma60_t, ma20_p, ma60_p):
            if ma20_p < ma60_p and ma20_t >= ma60_t:
                return True, "중장기 이동평균선 골든크로스(MA20/MA60) 발생이 관찰됩니다."

    if len(closes) >= 21:
        ma5_t  = _ma(closes, 5)
        ma20_t = _ma(closes, 20)
        ma5_p  = _ma(closes[:-1], 5)
        ma20_p = _ma(closes[:-1], 20)
        if None not in (ma5_t, ma20_t, ma5_p, ma20_p):
            if ma5_p < ma20_p and ma5_t >= ma20_t:
                return True, "단기 이동평균선 골든크로스(MA5/MA20) 발생이 관찰됩니다."

    return False, ""


def _detect_dead_cross(closes: list[float]) -> tuple[bool, str]:
    """
    데드크로스 탐지 (두 단계):
      1순위) MA20이 MA60을 하향 돌파
      2순위) MA5가 MA20을 하향 돌파
    """
    if len(closes) >= 62:
        ma20_t = _ma(closes, 20)
        ma60_t = _ma(closes, 60)
        ma20_p = _ma(closes[:-1], 20)
        ma60_p = _ma(closes[:-1], 60)
        if None not in (ma20_t, ma60_t, ma20_p, ma60_p):
            if ma20_p >= ma60_p and ma20_t < ma60_t:
                return True, "중장기 이동평균선 데드크로스(MA20/MA60) 발생이 관찰됩니다."

    if len(closes) >= 21:
        ma5_t  = _ma(closes, 5)
        ma20_t = _ma(closes, 20)
        ma5_p  = _ma(closes[:-1], 5)
        ma20_p = _ma(closes[:-1], 20)
        if None not in (ma5_t, ma20_t, ma5_p, ma20_p):
            if ma5_p >= ma20_p and ma5_t < ma20_t:
                return True, "단기 이동평균선 데드크로스(MA5/MA20) 발생이 관찰됩니다."

    return False, ""


def _detect_pullback(closes: list[float]) -> tuple[bool, str]:
    """
    눌림목 패턴:
      1) 최근 20일 고점 대비 -3%~-20% 조정
      2) 현재가가 MA20 또는 MA60의 ±2.5% 이내
      3) 최근 5일 중 최저점 이후 반등 흐름 확인
    """
    if len(closes) < 25:
        return False, ""
    today    = closes[-1]
    peak     = max(closes[-21:-1])
    if peak <= 0:
        return False, ""
    correction = (today - peak) / peak
    if not (-0.20 <= correction <= -0.03):
        return False, ""

    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60) if len(closes) >= 60 else None
    near_ma20 = ma20 and abs(today - ma20) / ma20 <= 0.025
    near_ma60 = ma60 and abs(today - ma60) / ma60 <= 0.025
    if not (near_ma20 or near_ma60):
        return False, ""

    # 반등 확인: 최근 5일 최저점이 오늘이 아니고, 최저점 이후 오늘이 더 높음
    last5    = closes[-6:]
    min_val  = min(last5)
    min_idx  = last5.index(min_val)
    if min_idx == len(last5) - 1 or today <= min_val:
        return False, ""

    support = "MA20" if near_ma20 else "MA60"
    return True, f"단기 조정 후 {support} 지지에서 눌림목 패턴이 관찰됩니다."


# ── 보조 지표 ─────────────────────────────────────────────────────

def _calc_ma_alignment(closes: list[float]) -> str:
    """이동평균 정배열/역배열/혼조 판단 (MA5 > MA20 > MA60 > MA120)."""
    vals = [v for v in (
        _ma(closes, 5),
        _ma(closes, 20),
        _ma(closes, 60),
        _ma(closes, 120),
    ) if v is not None]
    if len(vals) < 3:
        return "중립"
    if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
        return "정배열"
    if all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
        return "역배열"
    return "혼조"


def _calc_pattern_score(
    breakout: bool,
    new_high: bool,
    vol_breakout: bool,
    ma20_breakout: bool,
    ma60_breakout: bool,
    golden_cross: bool,
    dead_cross: bool,
    pullback: bool,
    alignment: str,
) -> float:
    score = 0.0
    if breakout:       score += 25.0
    if new_high:       score += 20.0
    if vol_breakout:   score += 15.0
    if ma20_breakout:  score += 15.0
    if ma60_breakout:  score += 20.0
    if golden_cross:   score += 25.0
    if dead_cross:     score -= 30.0
    if pullback:       score += 15.0
    if alignment == "정배열":   score += 10.0
    elif alignment == "역배열": score -= 10.0
    return max(-100.0, min(100.0, score))


def _determine_chart_signal(score: float, dead_cross: bool) -> str:
    if dead_cross and score < 0:
        return "하락주의"
    if score >= 60:   return "강한상승패턴"
    if score >= 30:   return "상승패턴"
    if score >= 5:    return "중립"
    if score >= -25:  return "약세"
    return "하락주의"


# ── AI 해설 ───────────────────────────────────────────────────────

def _sanitize(txt: Optional[str]) -> Optional[str]:
    if not txt:
        return txt
    for p in _BANNED:
        txt = txt.replace(p, "")
    return txt.strip() or None


def _call_chart_ai(
    stock_code: str,
    stock_name: str,
    metrics: dict,
    target_date: date,
) -> dict:
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return {}
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        def yn(v: bool) -> str:
            return "감지" if v else "미감지"

        def _pct_str(v) -> str:
            return f"{v:+.2f}%" if v is not None else "N/A"

        def _ratio_str(v) -> str:
            return f"{v:.2f}배" if v is not None else "N/A"

        prompt = (
            f"[기준일: {target_date}] 분석 종목: {stock_name}({stock_code})\n\n"
            f"■ 탐지된 패턴\n"
            f"  박스권 돌파: {yn(metrics['breakout_signal'])}\n"
            f"  신고가 근접: {yn(metrics['new_high_signal'])}\n"
            f"  거래량 동반 상승: {yn(metrics['volume_breakout_signal'])}\n"
            f"  MA20 돌파: {yn(metrics['ma20_breakout_signal'])}\n"
            f"  MA60 돌파: {yn(metrics['ma60_breakout_signal'])}\n"
            f"  골든크로스: {yn(metrics['golden_cross_signal'])}\n"
            f"  데드크로스: {yn(metrics['dead_cross_signal'])}\n"
            f"  눌림목 패턴: {yn(metrics['pullback_signal'])}\n\n"
            f"■ 이동평균 배열: {metrics['ma_alignment']}\n"
            f"■ 패턴 점수: {metrics['pattern_score']:.1f}pt ({metrics['chart_signal']})\n\n"
            f"■ 현재가 대비 지표\n"
            f"  MA20 대비: {_pct_str(metrics.get('price_vs_ma20'))}\n"
            f"  MA60 대비: {_pct_str(metrics.get('price_vs_ma60'))}\n"
            f"  52주 고점 대비: {_pct_str(metrics.get('price_vs_52w_high'))}\n"
            f"  거래량 비율(20일 평균): {_ratio_str(metrics.get('volume_ratio_20d'))}\n\n"
            "위 데이터를 바탕으로 JSON 형식의 차트 패턴 해설을 작성하세요."
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
            "ai_chart_summary":   _sanitize(raw.get("ai_chart_summary")),
            "ai_pattern_comment": _sanitize(raw.get("ai_pattern_comment")),
            "ai_trend_comment":   _sanitize(raw.get("ai_trend_comment")),
        }
    except Exception as e:
        logger.error(f"[차트패턴AI] {stock_code} 오류: {e}")
        return {}


# ── DB 저장 ───────────────────────────────────────────────────────

def _upsert(session, stock_code: str, analysis_date: date, data: dict) -> None:
    fields = {k: v for k, v in data.items() if k not in ("stock_code", "analysis_date")}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(
        "INSERT INTO chart_pattern_analysis_results "
        "(stock_code, analysis_date, "
        + ", ".join(fields.keys())
        + ") VALUES (:stock_code, :analysis_date, "
        + ", ".join(f":{k}" for k in fields)
        + f") ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    session.execute(sql, {"stock_code": stock_code, "analysis_date": analysis_date, **fields})
    session.commit()


# ── 메인 분석 ────────────────────────────────────────────────────

def analyze_chart_pattern(
    stock_code: str,
    analysis_date: date,
    with_ai: bool = True,
) -> dict:
    """단일 종목 차트 패턴 분석 → DB 저장."""
    session = get_db_session()
    try:
        stock = session.execute(
            select(Stock).where(Stock.stock_code == stock_code)
        ).scalar_one_or_none()
        stock_name = stock.stock_name if stock else stock_code

        prices = _load_prices(session, stock_code, analysis_date)
        if not prices or len(prices) < 22:
            return {
                "status": "no_data",
                "stock_code": stock_code,
                "message": "가격 데이터 부족 (최소 22일 필요)",
            }

        closes  = [p["close"]  for p in prices]
        volumes = [p["volume"] for p in prices]

        # ── 패턴 탐지 ──────────────────────────────────────────────
        breakout,     breakout_msg  = _detect_box_breakout(closes)
        new_high,     new_high_msg  = _detect_new_high(closes)
        vol_brk,      vol_brk_msg   = _detect_volume_breakout(closes, volumes)
        ma20_brk,     ma20_brk_msg  = _detect_ma20_breakout(closes)
        ma60_brk,     ma60_brk_msg  = _detect_ma60_breakout(closes)
        golden_cross, golden_msg    = _detect_golden_cross(closes)
        dead_cross,   dead_msg      = _detect_dead_cross(closes)
        pullback,     pullback_msg  = _detect_pullback(closes)
        alignment                   = _calc_ma_alignment(closes)

        # ── 보조 지표 ──────────────────────────────────────────────
        today_close = closes[-1]
        ma20        = _ma(closes, 20)
        ma60        = _ma(closes, 60)
        hist        = closes[:-1]
        high_52w    = max(hist[-250:]) if len(hist) >= 20 else None
        avg_vol_20  = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None

        def _pct(val: float, base: Optional[float]) -> Optional[float]:
            if base and base > 0:
                return round((val - base) / base * 100, 2)
            return None

        score  = _calc_pattern_score(
            breakout, new_high, vol_brk, ma20_brk, ma60_brk,
            golden_cross, dead_cross, pullback, alignment,
        )
        signal = _determine_chart_signal(score, dead_cross)

        pattern_msgs = [m for m in [
            breakout_msg, new_high_msg, vol_brk_msg,
            ma20_brk_msg, ma60_brk_msg, golden_msg,
            dead_msg, pullback_msg,
        ] if m]

        # 중장기 이동평균 정배열 여부 추가 문구
        if alignment == "정배열":
            pattern_msgs.append("중장기 이동평균선 정배열 흐름이 유지되고 있습니다.")

        metrics: dict = {
            "breakout_signal":        breakout,
            "new_high_signal":        new_high,
            "volume_breakout_signal": vol_brk,
            "ma20_breakout_signal":   ma20_brk,
            "ma60_breakout_signal":   ma60_brk,
            "golden_cross_signal":    golden_cross,
            "dead_cross_signal":      dead_cross,
            "pullback_signal":        pullback,
            "ma_alignment":           alignment,
            "pattern_score":          round(score, 2),
            "chart_signal":           signal,
            "price_vs_ma20":          _pct(today_close, ma20),
            "price_vs_ma60":          _pct(today_close, ma60),
            "price_vs_52w_high":      _pct(today_close, high_52w),
            "volume_ratio_20d":       round(volumes[-1] / avg_vol_20, 2) if avg_vol_20 else None,
            "pattern_descriptions":   " | ".join(pattern_msgs) if pattern_msgs else None,
        }

        if with_ai:
            ai = _call_chart_ai(stock_code, stock_name, metrics, analysis_date)
            metrics.update(ai)

        _upsert(session, stock_code, analysis_date, metrics)

        logger.info(
            f"[차트패턴] {stock_code} {stock_name} "
            f"점수={score:.1f} 시그널={signal} "
            f"골든크로스={golden_cross} 데드크로스={dead_cross} "
            f"박스권돌파={breakout} 신고가={new_high}"
        )
        return {"status": "success", "stock_code": stock_code, "stock_name": stock_name, **metrics}

    except Exception as e:
        logger.error(f"[차트패턴] {stock_code} 분석 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "stock_code": stock_code, "message": str(e)}
    finally:
        session.close()


# ── 배치 ─────────────────────────────────────────────────────────

def run_chart_pattern_batch(
    analysis_date: Optional[date] = None,
    limit: int = 100,
    delay_sec: float = 0.05,
) -> dict:
    """관심종목 + 분석점수 상위 종목 차트 패턴 배치 분석."""
    if analysis_date is None:
        analysis_date = date.today()

    session = get_db_session()
    try:
        from app.models.watchlist import WatchlistItem
        watchlist_codes = list(
            session.execute(
                select(WatchlistItem.stock_code)
            ).scalars().all()
        )
        from app.models.analysis import StockAnalysisResult
        top_codes = list(
            session.execute(
                select(StockAnalysisResult.stock_code)
                .where(StockAnalysisResult.analysis_date == analysis_date)
                .order_by(StockAnalysisResult.bullish_score.desc())
                .limit(limit)
            ).scalars().all()
        )
    finally:
        session.close()

    targets = list(dict.fromkeys(watchlist_codes + top_codes))[:limit]
    if not targets:
        return {"status": "no_data", "message": f"{analysis_date} 분석 대상 종목 없음"}

    success = skipped = errors = 0
    for code in targets:
        r = analyze_chart_pattern(code, analysis_date, with_ai=True)
        if r.get("status") == "success":
            success += 1
        elif r.get("status") == "no_data":
            skipped += 1
        else:
            errors += 1
        if delay_sec > 0:
            time.sleep(delay_sec)

    return {
        "status": "success" if errors == 0 else "partial",
        "analysis_date": str(analysis_date),
        "total": len(targets),
        "success": success,
        "skipped": skipped,
        "errors": errors,
    }


# ── DB 읽기 ───────────────────────────────────────────────────────

def _row_to_dict(row: ChartPatternAnalysisResult) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    return {
        "stock_code":    row.stock_code,
        "analysis_date": str(row.analysis_date),
        # 시그널
        "breakout_signal":        bool(row.breakout_signal),
        "new_high_signal":        bool(row.new_high_signal),
        "volume_breakout_signal": bool(row.volume_breakout_signal),
        "ma20_breakout_signal":   bool(row.ma20_breakout_signal),
        "ma60_breakout_signal":   bool(row.ma60_breakout_signal),
        "golden_cross_signal":    bool(row.golden_cross_signal),
        "dead_cross_signal":      bool(row.dead_cross_signal),
        "pullback_signal":        bool(row.pullback_signal),
        # 종합
        "ma_alignment":  row.ma_alignment or "중립",
        "pattern_score": _f(row.pattern_score),
        "chart_signal":  row.chart_signal or "중립",
        # 보조 지표
        "price_vs_ma20":     _f(row.price_vs_ma20),
        "price_vs_ma60":     _f(row.price_vs_ma60),
        "price_vs_52w_high": _f(row.price_vs_52w_high),
        "volume_ratio_20d":  _f(row.volume_ratio_20d),
        # 설명
        "pattern_descriptions": row.pattern_descriptions,
        # AI
        "ai_chart_summary":   row.ai_chart_summary,
        "ai_pattern_comment": row.ai_pattern_comment,
        "ai_trend_comment":   row.ai_trend_comment,
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def get_chart_pattern(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> Optional[dict]:
    """단일 종목 차트 패턴 분석 결과 조회."""
    session = get_db_session()
    try:
        q = select(ChartPatternAnalysisResult).where(
            ChartPatternAnalysisResult.stock_code == stock_code
        )
        if analysis_date:
            q = q.where(ChartPatternAnalysisResult.analysis_date == analysis_date)
        q = q.order_by(ChartPatternAnalysisResult.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_chart_pattern_top(
    analysis_date: Optional[date] = None,
    limit: int = 50,
    signal: Optional[str] = None,
    pattern: Optional[str] = None,
) -> list[dict]:
    """
    차트 패턴 점수 상위 종목 목록.

    pattern 필터: golden_cross / breakout / new_high / volume / pullback
    """
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(ChartPatternAnalysisResult.analysis_date)
                .order_by(ChartPatternAnalysisResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(ChartPatternAnalysisResult).where(
            ChartPatternAnalysisResult.analysis_date == analysis_date
        )
        if signal:
            q = q.where(ChartPatternAnalysisResult.chart_signal == signal)

        _pattern_col_map = {
            "golden_cross": ChartPatternAnalysisResult.golden_cross_signal,
            "breakout":     ChartPatternAnalysisResult.breakout_signal,
            "new_high":     ChartPatternAnalysisResult.new_high_signal,
            "volume":       ChartPatternAnalysisResult.volume_breakout_signal,
            "pullback":     ChartPatternAnalysisResult.pullback_signal,
        }
        if pattern in _pattern_col_map:
            q = q.where(_pattern_col_map[pattern].is_(True))

        q = q.order_by(ChartPatternAnalysisResult.pattern_score.desc()).limit(limit)
        rows = session.execute(q).scalars().all()
        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()
