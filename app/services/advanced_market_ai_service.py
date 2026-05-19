"""
종합 시장 AI 해설 서비스

모든 분석 데이터를 종합하여 시장 전체에 대한 5개 관점 AI 해설을 생성합니다.

분석 소스:
  - market_indices              : KOSPI / KOSDAQ 지수 흐름
  - stock_analysis_results      : 강세/약세 신호 분포
  - supply_demand_analysis      : 외국인·기관 수급, 공매도
  - news_sentiment_results      : 뉴스 감성 분포
  - chart_pattern_analysis      : 차트 신호 분포
  - theme_analysis_results      : 테마별 수익률
  - market_leader_summary       : 시장 주도주 요약
  - theme_rotation_summary      : 테마 순환 요약
  - risk_analysis_results       : 위험 등급 분포
  - disclosure_ai_analysis      : 오늘의 위험 공시

AI 출력:
  ai_market_flow_summary   — 전체 시장 흐름 (지수+강약세+자금 방향)
  ai_stock_summary         — 주요 종목 흐름 (주도주+차트+수급 연계)
  ai_risk_summary          — 위험 요인 종합 (과열+공시+뉴스 악재)
  ai_theme_summary         — 테마 순환 흐름 (순환매+주도+이탈)
  ai_supply_demand_summary — 수급 흐름 (외국인/기관+공매도+테마)

주의: 본 결과는 참고용 분석 정보이며 투자 권유가 아닙니다.
"""
import json
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select, text

from app.config import settings
from app.database import get_db_session
from app.models.advanced_market_ai import AdvancedMarketAI

logger = logging.getLogger(__name__)

DISCLAIMER = "본 분석은 참고용이며 투자 권유가 아닙니다."

_AI_SYSTEM = """당신은 한국 주식 시장 전문 분석가입니다.

[역할]
다양한 분석 데이터를 교차 검증하여 당일 시장 전체에 대한
전문적이고 이해하기 쉬운 종합 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "지금 사야함", "지금 팔아야함", "급등 확정", "수익 보장"
3. 허용 표현: "흐름 관찰", "수급 유입 확인", "모니터링 권장", "주의 구간"
4. 여러 데이터 소스를 교차 검증하여 연계 분석
5. 한국어만 사용
6. 각 해설은 2~4 문장의 자연스러운 서술형으로 작성

[출력 형식 — JSON]
{
  "ai_market_flow_summary":   "...",
  "ai_stock_summary":         "...",
  "ai_risk_summary":          "...",
  "ai_theme_summary":         "...",
  "ai_supply_demand_summary": "..."
}"""

_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]


# ── 데이터 로딩 ──────────────────────────────────────────────────────────────

def _load_market_indices(target_date: date, session) -> dict:
    """KOSPI / KOSDAQ 최근 5거래일 지수."""
    since = target_date - timedelta(days=10)
    rows = session.execute(text("""
        SELECT index_name, trade_date, close_value, change_rate
        FROM market_indices
        WHERE trade_date BETWEEN :s AND :e
          AND index_name IN ('KOSPI', 'KOSDAQ')
        ORDER BY index_name, trade_date DESC
    """), {"s": since, "e": target_date}).fetchall()

    result: dict = {}
    for row in rows:
        name = row[0]
        if name not in result:
            result[name] = []
        result[name].append({
            "date": str(row[1]),
            "close": float(row[2]) if row[2] else None,
            "change_rate": float(row[3]) if row[3] else None,
        })
    return result


def _load_signal_distribution(target_date: date, session) -> dict:
    """강세/약세 신호 카운트 + 상위 5종목."""
    since = target_date - timedelta(days=3)

    # 신호 분포
    dist_rows = session.execute(text("""
        SELECT final_signal, COUNT(*) as cnt
        FROM stock_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
        GROUP BY final_signal
    """), {"s": since, "e": target_date}).fetchall()
    signal_dist = {r[0]: int(r[1]) for r in dist_rows if r[0]}

    # 강세 상위 5
    top5_rows = session.execute(text("""
        SELECT sar.stock_code, s.stock_name, sar.bullish_score, sar.final_signal
        FROM stock_analysis_results sar
        LEFT JOIN stocks s ON s.stock_code = sar.stock_code
        WHERE sar.analysis_date = :d
          AND sar.final_signal IN ('강한 강세', '강세')
        ORDER BY sar.bullish_score DESC
        LIMIT 5
    """), {"d": target_date}).fetchall()
    top_bullish = [{"code": r[0], "name": r[1] or r[0], "score": float(r[2] or 0), "signal": r[3]}
                   for r in top5_rows]

    # 약세 상위 5
    bot5_rows = session.execute(text("""
        SELECT sar.stock_code, s.stock_name, sar.bullish_score, sar.final_signal
        FROM stock_analysis_results sar
        LEFT JOIN stocks s ON s.stock_code = sar.stock_code
        WHERE sar.analysis_date = :d
          AND sar.final_signal IN ('강한 약세', '약세')
        ORDER BY sar.bullish_score ASC
        LIMIT 5
    """), {"d": target_date}).fetchall()
    top_bearish = [{"code": r[0], "name": r[1] or r[0], "score": float(r[2] or 0), "signal": r[3]}
                   for r in bot5_rows]

    return {"signal_dist": signal_dist, "top_bullish": top_bullish, "top_bearish": top_bearish}


def _load_supply_demand(target_date: date, session) -> dict:
    since = target_date - timedelta(days=3)
    rows = session.execute(text("""
        SELECT supply_signal,
               AVG(foreign_net_buy_5d) AS avg_foreign,
               AVG(institution_net_buy_5d) AS avg_inst,
               AVG(short_sell_ratio) AS avg_short,
               COUNT(*) AS cnt
        FROM supply_demand_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
        GROUP BY supply_signal
    """), {"s": since, "e": target_date}).fetchall()

    signal_dist: dict = {}
    totals = {"foreign_buy": 0, "institution_buy": 0, "short_sell_avg": 0.0, "n": 0}
    for r in rows:
        signal_dist[r[0] or "불명"] = int(r[4])
        totals["n"] += int(r[4])
        totals["foreign_buy"] += (float(r[1]) or 0) * int(r[4])
        totals["institution_buy"] += (float(r[2]) or 0) * int(r[4])
        totals["short_sell_avg"] += (float(r[3]) or 0) * int(r[4])

    n = totals["n"] or 1
    return {
        "signal_dist": signal_dist,
        "avg_foreign_net_5d": round(totals["foreign_buy"] / n, 2),
        "avg_institution_net_5d": round(totals["institution_buy"] / n, 2),
        "avg_short_sell_ratio": round(totals["short_sell_avg"] / n, 2),
    }


def _load_news_sentiment(target_date: date, session) -> dict:
    since = target_date - timedelta(days=3)
    rows = session.execute(text("""
        SELECT news_sentiment_signal, COUNT(*) as cnt,
               AVG(news_sentiment_score) as avg_score
        FROM news_sentiment_results
        WHERE analysis_date BETWEEN :s AND :e
        GROUP BY news_sentiment_signal
    """), {"s": since, "e": target_date}).fetchall()

    signal_dist: dict = {}
    weighted_score = 0.0
    total_n = 0
    for r in rows:
        cnt = int(r[1])
        signal_dist[r[0] or "불명"] = cnt
        weighted_score += (float(r[2]) or 0) * cnt
        total_n += cnt

    return {
        "signal_dist": signal_dist,
        "avg_sentiment_score": round(weighted_score / (total_n or 1), 2),
    }


def _load_chart_patterns(target_date: date, session) -> dict:
    since = target_date - timedelta(days=3)
    rows = session.execute(text("""
        SELECT
            SUM(CASE WHEN golden_cross_signal THEN 1 ELSE 0 END) AS golden,
            SUM(CASE WHEN dead_cross_signal   THEN 1 ELSE 0 END) AS dead,
            SUM(CASE WHEN breakout_signal     THEN 1 ELSE 0 END) AS breakout,
            SUM(CASE WHEN new_high_signal     THEN 1 ELSE 0 END) AS new_high,
            SUM(CASE WHEN volume_breakout_signal THEN 1 ELSE 0 END) AS vol_brk,
            SUM(CASE WHEN pullback_signal     THEN 1 ELSE 0 END) AS pullback,
            COUNT(*) AS total
        FROM chart_pattern_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
    """), {"s": since, "e": target_date}).fetchone()

    if not rows or not rows[6]:
        return {}

    return {
        "golden_cross": int(rows[0] or 0),
        "dead_cross": int(rows[1] or 0),
        "breakout": int(rows[2] or 0),
        "new_high": int(rows[3] or 0),
        "volume_breakout": int(rows[4] or 0),
        "pullback": int(rows[5] or 0),
        "total": int(rows[6]),
    }


def _load_theme_analysis(target_date: date, session) -> dict:
    since = target_date - timedelta(days=3)
    # 테마별 상위 5 강세
    top_rows = session.execute(text("""
        SELECT theme_name, AVG(avg_return_1d) as avg_ret, theme_signal
        FROM theme_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
          AND theme_signal IN ('매우 강세', '강세 흐름')
        GROUP BY theme_name, theme_signal
        ORDER BY avg_ret DESC
        LIMIT 5
    """), {"s": since, "e": target_date}).fetchall()
    top_themes = [{"theme": r[0], "avg_return_1d": round(float(r[1] or 0), 2), "signal": r[2]}
                  for r in top_rows]

    # 테마별 상위 5 약세
    weak_rows = session.execute(text("""
        SELECT theme_name, AVG(avg_return_1d) as avg_ret, theme_signal
        FROM theme_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
          AND theme_signal IN ('약세 흐름', '하락 주의')
        GROUP BY theme_name, theme_signal
        ORDER BY avg_ret ASC
        LIMIT 5
    """), {"s": since, "e": target_date}).fetchall()
    weak_themes = [{"theme": r[0], "avg_return_1d": round(float(r[1] or 0), 2), "signal": r[2]}
                   for r in weak_rows]

    return {"top_themes": top_themes, "weak_themes": weak_themes}


def _load_market_leader_summary(target_date: date, session) -> dict:
    since = target_date - timedelta(days=5)
    row = session.execute(text("""
        SELECT top_leaders, dominant_themes, ai_market_summary,
               ai_theme_flow, leader_count
        FROM market_leader_summary
        WHERE analysis_date BETWEEN :s AND :e
        ORDER BY analysis_date DESC
        LIMIT 1
    """), {"s": since, "e": target_date}).fetchone()

    if not row:
        return {}

    def _safe_json(v):
        if not v:
            return []
        try:
            return json.loads(v)
        except Exception:
            return []

    return {
        "top_leaders": _safe_json(row[0])[:5],
        "dominant_themes": _safe_json(row[1])[:5],
        "leader_count": int(row[4] or 0),
    }


def _load_theme_rotation_summary(target_date: date, session) -> dict:
    since = target_date - timedelta(days=5)
    row = session.execute(text("""
        SELECT rotation_inflow, rotation_outflow, rotation_chain,
               ai_rotation_overview, ai_theme_flow_comment
        FROM theme_rotation_summary
        WHERE analysis_date BETWEEN :s AND :e
        ORDER BY analysis_date DESC
        LIMIT 1
    """), {"s": since, "e": target_date}).fetchone()

    if not row:
        return {}

    def _safe_json(v):
        if not v:
            return []
        try:
            return json.loads(v)
        except Exception:
            return []

    return {
        "rotation_inflow": _safe_json(row[0]),
        "rotation_outflow": _safe_json(row[1]),
        "rotation_chain": row[2] or "",
    }


def _load_risk_distribution(target_date: date, session) -> dict:
    since = target_date - timedelta(days=3)
    rows = session.execute(text("""
        SELECT risk_grade, COUNT(*) as cnt
        FROM risk_analysis_results
        WHERE analysis_date BETWEEN :s AND :e
        GROUP BY risk_grade
    """), {"s": since, "e": target_date}).fetchall()
    return {r[0] or "불명": int(r[1]) for r in rows}


def _load_high_risk_disclosures(target_date: date, session) -> list:
    since = target_date - timedelta(days=1)
    rows = session.execute(text("""
        SELECT d.stock_code, s.stock_name, d.title, da.ai_disclosure_risk
        FROM disclosures d
        LEFT JOIN stocks s ON s.stock_code = d.stock_code
        LEFT JOIN disclosure_ai_analysis da ON da.disclosure_id = d.id
        WHERE d.report_date BETWEEN :s AND :e
          AND da.ai_disclosure_risk IN ('높음', '매우 높음')
        ORDER BY da.ai_disclosure_risk DESC, d.report_date DESC
        LIMIT 10
    """), {"s": since, "e": target_date}).fetchall()

    return [{"code": r[0], "name": r[1] or r[0], "title": r[2], "risk": r[3]} for r in rows]


def _load_all_data(target_date: date) -> dict:
    with get_db_session() as session:
        indices = _load_market_indices(target_date, session)
        signals = _load_signal_distribution(target_date, session)
        supply  = _load_supply_demand(target_date, session)
        news    = _load_news_sentiment(target_date, session)
        charts  = _load_chart_patterns(target_date, session)
        themes  = _load_theme_analysis(target_date, session)
        leaders = _load_market_leader_summary(target_date, session)
        rotation = _load_theme_rotation_summary(target_date, session)
        risk_dist = _load_risk_distribution(target_date, session)
        hi_risk_disc = _load_high_risk_disclosures(target_date, session)

    return {
        "report_date": str(target_date),
        "market_indices": indices,
        "signal_distribution": signals,
        "supply_demand": supply,
        "news_sentiment": news,
        "chart_patterns": charts,
        "theme_analysis": themes,
        "market_leader_summary": leaders,
        "theme_rotation_summary": rotation,
        "risk_distribution": risk_dist,
        "high_risk_disclosures": hi_risk_disc,
    }


# ── 프롬프트 구성 ──────────────────────────────────────────────────────────────

def _build_prompt(data: dict) -> str:
    idx = data.get("market_indices", {})
    sig = data.get("signal_distribution", {})
    sup = data.get("supply_demand", {})
    nws = data.get("news_sentiment", {})
    cht = data.get("chart_patterns", {})
    thm = data.get("theme_analysis", {})
    ldr = data.get("market_leader_summary", {})
    rot = data.get("theme_rotation_summary", {})
    rsk = data.get("risk_distribution", {})
    hrd = data.get("high_risk_disclosures", [])

    lines = [f"=== 분석 기준일: {data.get('report_date', '불명')} ===\n"]

    # 지수
    lines.append("## 1. 시장 지수")
    for name, hist in idx.items():
        if hist:
            latest = hist[0]
            cr = f"{latest['change_rate']:+.2f}%" if latest.get("change_rate") is not None else "N/A"
            lines.append(f"  {name}: {latest.get('close', 'N/A')} ({cr})")
    lines.append("")

    # 강약세 신호
    lines.append("## 2. 강약세 신호 분포")
    for sig_name, cnt in sig.get("signal_dist", {}).items():
        lines.append(f"  {sig_name}: {cnt}종목")
    if sig.get("top_bullish"):
        lines.append("  강세 상위: " + ", ".join(
            f"{s['name']}({s['score']:.0f}pt)" for s in sig["top_bullish"]))
    if sig.get("top_bearish"):
        lines.append("  약세 상위: " + ", ".join(
            f"{s['name']}({s['score']:.0f}pt)" for s in sig["top_bearish"]))
    lines.append("")

    # 수급
    lines.append("## 3. 수급 분석")
    lines.append(f"  신호 분포: {sup.get('signal_dist', {})}")
    lines.append(f"  외국인 5일 순매수 평균: {sup.get('avg_foreign_net_5d', 0):+,.0f}")
    lines.append(f"  기관 5일 순매수 평균:   {sup.get('avg_institution_net_5d', 0):+,.0f}")
    lines.append(f"  평균 공매도 비중:        {sup.get('avg_short_sell_ratio', 0):.2f}%")
    lines.append("")

    # 뉴스 감성
    lines.append("## 4. 뉴스 감성")
    lines.append(f"  신호 분포: {nws.get('signal_dist', {})}")
    lines.append(f"  평균 감성 점수: {nws.get('avg_sentiment_score', 0):.2f}")
    lines.append("")

    # 차트 패턴
    lines.append("## 5. 차트 패턴 신호")
    if cht:
        lines.append(f"  골든크로스: {cht.get('golden_cross', 0)}종목  |  데드크로스: {cht.get('dead_cross', 0)}종목")
        lines.append(f"  박스권 돌파: {cht.get('breakout', 0)}종목   |  신고가: {cht.get('new_high', 0)}종목")
        lines.append(f"  거래량 돌파: {cht.get('volume_breakout', 0)}종목  |  눌림목: {cht.get('pullback', 0)}종목")
    else:
        lines.append("  (데이터 없음)")
    lines.append("")

    # 테마
    lines.append("## 6. 테마 분석")
    if thm.get("top_themes"):
        lines.append("  강세 테마: " + ", ".join(
            f"{t['theme']}({t['avg_return_1d']:+.2f}%)" for t in thm["top_themes"]))
    if thm.get("weak_themes"):
        lines.append("  약세 테마: " + ", ".join(
            f"{t['theme']}({t['avg_return_1d']:+.2f}%)" for t in thm["weak_themes"]))
    lines.append("")

    # 시장 주도주
    lines.append("## 7. 시장 주도주")
    if ldr.get("top_leaders"):
        names = [ld.get("name") or ld.get("stock_name") or ld.get("stock_code", "?")
                 for ld in ldr["top_leaders"]]
        lines.append("  주도주: " + ", ".join(str(n) for n in names))
    if ldr.get("dominant_themes"):
        lines.append("  주도 테마: " + ", ".join(str(t) for t in ldr["dominant_themes"]))
    lines.append(f"  주도주 수: {ldr.get('leader_count', 0)}종목")
    lines.append("")

    # 테마 순환
    lines.append("## 8. 테마 순환")
    if rot.get("rotation_chain"):
        lines.append(f"  순환 흐름: {rot['rotation_chain']}")
    if rot.get("rotation_inflow"):
        lines.append(f"  유입 테마: {', '.join(str(t) for t in rot['rotation_inflow'][:5])}")
    if rot.get("rotation_outflow"):
        lines.append(f"  이탈 테마: {', '.join(str(t) for t in rot['rotation_outflow'][:5])}")
    lines.append("")

    # 위험 분포
    lines.append("## 9. 위험 등급 분포")
    for grade, cnt in rsk.items():
        lines.append(f"  {grade}: {cnt}종목")
    lines.append("")

    # 고위험 공시
    lines.append("## 10. 고위험 공시")
    if hrd:
        for d in hrd[:5]:
            lines.append(f"  [{d['risk']}] {d['name']} — {d['title']}")
    else:
        lines.append("  (해당 없음)")
    lines.append("")

    lines.append("""---
위 데이터를 교차 검증하여 아래 5개 항목에 대한 종합 해설을 작성하세요.
각 항목은 2~4 문장의 자연스러운 서술형으로 데이터 간 연계 분석을 포함해야 합니다.

  ai_market_flow_summary   : 전체 시장 흐름 — 지수 방향, 강세·약세 종목 비율, 자금 방향 종합
  ai_stock_summary         : 주요 종목 흐름 — 주도주, 차트 패턴과 수급 연계 분석
  ai_risk_summary          : 위험 요인 종합 — 과열 신호, 공시 위험, 뉴스 악재 교차 분석
  ai_theme_summary         : 테마 순환 흐름 — 강세 테마, 이탈 테마, 순환매 방향
  ai_supply_demand_summary : 수급 흐름 — 외국인/기관 방향, 공매도 수준, 테마 수급 연계
""")

    return "\n".join(lines)


# ── AI 호출 ───────────────────────────────────────────────────────────────────

def _call_ai(prompt: str, model: str) -> dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content or "{}"
        result = json.loads(raw)
        for key in ("ai_market_flow_summary", "ai_stock_summary", "ai_risk_summary",
                    "ai_theme_summary", "ai_supply_demand_summary"):
            text_val = result.get(key, "")
            for banned in _BANNED:
                text_val = text_val.replace(banned, "[참고용]")
            result[key] = text_val
        return result
    except Exception as e:
        logger.error(f"Advanced market AI 호출 실패: {e}")
        return {}


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def generate_advanced_market_ai(
    report_date: Optional[date] = None,
    model: str = "gpt-4o-mini",
    force_regenerate: bool = False,
) -> dict:
    target_date = report_date or date.today()

    if not force_regenerate:
        existing = get_advanced_market_ai(target_date)
        if existing and existing.get("ai_market_flow_summary"):
            logger.info(f"[AdvancedMarketAI] {target_date} 기존 결과 반환")
            return {"status": "exists", "data": existing}

    logger.info(f"[AdvancedMarketAI] {target_date} 데이터 수집 시작")
    data = _load_all_data(target_date)

    # 데이터 충분성 체크
    total_signals = sum(data["signal_distribution"].get("signal_dist", {}).values())
    if total_signals == 0:
        logger.warning(f"[AdvancedMarketAI] {target_date} 분석 데이터 부족")
        return {"status": "no_data", "message": "분석 데이터가 부족합니다.", "date": str(target_date)}

    prompt = _build_prompt(data)
    logger.info(f"[AdvancedMarketAI] AI 호출 ({model})")
    ai_result = _call_ai(prompt, model)

    if not ai_result:
        return {"status": "ai_error", "message": "AI 응답 실패", "date": str(target_date)}

    data_context = json.dumps({
        "signal_counts": data["signal_distribution"].get("signal_dist"),
        "theme_top": [t["theme"] for t in data["theme_analysis"].get("top_themes", [])],
        "risk_dist": data["risk_distribution"],
        "leader_count": data["market_leader_summary"].get("leader_count", 0),
        "rotation_chain": data["theme_rotation_summary"].get("rotation_chain", ""),
    }, ensure_ascii=False)

    with get_db_session() as session:
        session.execute(text("""
            INSERT INTO advanced_market_ai
              (report_date, ai_market_flow_summary, ai_stock_summary,
               ai_risk_summary, ai_theme_summary, ai_supply_demand_summary,
               data_context, model_used)
            VALUES
              (:d, :mf, :ss, :rs, :ts, :sds, :ctx, :mdl)
            ON DUPLICATE KEY UPDATE
              ai_market_flow_summary   = VALUES(ai_market_flow_summary),
              ai_stock_summary         = VALUES(ai_stock_summary),
              ai_risk_summary          = VALUES(ai_risk_summary),
              ai_theme_summary         = VALUES(ai_theme_summary),
              ai_supply_demand_summary = VALUES(ai_supply_demand_summary),
              data_context             = VALUES(data_context),
              model_used               = VALUES(model_used),
              updated_at               = NOW()
        """), {
            "d":   target_date,
            "mf":  ai_result.get("ai_market_flow_summary", ""),
            "ss":  ai_result.get("ai_stock_summary", ""),
            "rs":  ai_result.get("ai_risk_summary", ""),
            "ts":  ai_result.get("ai_theme_summary", ""),
            "sds": ai_result.get("ai_supply_demand_summary", ""),
            "ctx": data_context,
            "mdl": model,
        })
        session.commit()

    logger.info(f"[AdvancedMarketAI] {target_date} 저장 완료")
    return {
        "status": "generated",
        "report_date": str(target_date),
        "model_used": model,
        "data": {
            "report_date": str(target_date),
            **{k: ai_result.get(k, "") for k in (
                "ai_market_flow_summary", "ai_stock_summary",
                "ai_risk_summary", "ai_theme_summary", "ai_supply_demand_summary",
            )},
        },
    }


def get_advanced_market_ai(report_date: Optional[date] = None) -> Optional[dict]:
    with get_db_session() as session:
        if report_date:
            row = session.execute(text("""
                SELECT report_date, ai_market_flow_summary, ai_stock_summary,
                       ai_risk_summary, ai_theme_summary, ai_supply_demand_summary,
                       model_used, created_at, updated_at
                FROM advanced_market_ai
                WHERE report_date = :d
                LIMIT 1
            """), {"d": report_date}).fetchone()
        else:
            row = session.execute(text("""
                SELECT report_date, ai_market_flow_summary, ai_stock_summary,
                       ai_risk_summary, ai_theme_summary, ai_supply_demand_summary,
                       model_used, created_at, updated_at
                FROM advanced_market_ai
                ORDER BY report_date DESC
                LIMIT 1
            """)).fetchone()

    if not row:
        return None

    return {
        "report_date": str(row[0]),
        "ai_market_flow_summary":   row[1],
        "ai_stock_summary":         row[2],
        "ai_risk_summary":          row[3],
        "ai_theme_summary":         row[4],
        "ai_supply_demand_summary": row[5],
        "model_used":  row[6],
        "created_at":  str(row[7]) if row[7] else None,
        "updated_at":  str(row[8]) if row[8] else None,
    }
