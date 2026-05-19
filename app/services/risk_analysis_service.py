"""
종목 위험도 분석 서비스

6개 데이터 소스를 결합하여 종목별 위험 등급과 세부 위험 점수를 산출합니다.

분석 기준:
  - 변동성 위험       : volatility_20d, daily_return, RSI 극단
  - 급등·과열 위험     : RSI 과매수, 5일 수익률, 거래량 급증, 신고가
  - 공시 위험         : disclosure AI 위험 등급, 최근 위험 공시 수
  - 뉴스 악재 위험     : news_sentiment_signal, 악재 비중
  - 실적 악화 위험     : fundamental_signal, 부채비율, 영업이익 감소율
  - 수급 불균형 위험   : 공매도 비중, 외국인·기관 5일 순매도, supply_signal

위험 등급: 안정 / 보통 / 주의 / 고위험 / 과열주의

주의:
  - 투자 추천, 매수/매도 권유 시스템이 아닙니다.
  - 모든 결과는 참고용 위험 분석 정보입니다.
"""
import json
import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, text

from app.config import settings
from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.chart_pattern_analysis_result import ChartPatternAnalysisResult
from app.models.disclosure import Disclosure
from app.models.disclosure_ai_analysis import DisclosureAIAnalysis
from app.models.fundamental_analysis_result import FundamentalAnalysisResult
from app.models.news_sentiment_result import NewsSentimentResult
from app.models.risk_analysis_result import RiskAnalysisResult
from app.models.stock import Stock
from app.models.supply_demand_analysis import SupplyDemandAnalysis

logger = logging.getLogger(__name__)

DISCLAIMER = "본 위험도 분석은 참고용이며 투자 권유가 아닙니다."
_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승", "지금 팔아야",
]

_AI_SYSTEM = """당신은 한국 주식 종목 위험도 분석 전문가입니다.

[역할]
다양한 위험 지표를 종합하여 종목의 위험 요인을 평가하고
투자자가 이해할 수 있는 위험 관리 관점의 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "지금 사야함", "지금 팔아야함", "급등 확정"
3. 허용 표현: "점검 필요", "모니터링 권장", "리스크 확인", "주의 구간"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_risk_summary": "위험 요인 종합 평가 1~2문장",
  "ai_risk_factors": "주요 위험 요인 상세 설명 1~2문장",
  "ai_risk_action": "위험 관리 관점 제언 1문장 (매수·매도 언급 금지)"
}"""


# ── 위험 점수 계산 ─────────────────────────────────────────────────

def _calc_volatility_risk(
    sar: Optional[StockAnalysisResult],
) -> tuple[float, list[str]]:
    """변동성 위험 (0-100)."""
    score = 0.0
    factors: list[str] = []

    if not sar:
        return 15.0, []

    vol = float(sar.volatility_20d or 0)
    if vol >= 5:
        score += 60
        factors.append(f"변동성 과대({vol:.1f}%)")
    elif vol >= 3:
        score += 40
        factors.append(f"변동성 확대 구간({vol:.1f}%)")
    elif vol >= 2:
        score += 22
    elif vol >= 1:
        score += 10

    dr = abs(float(sar.daily_return or 0))
    if dr >= 8:
        score += 30
        factors.append(f"일간 급변동({dr:+.1f}%)")
    elif dr >= 5:
        score += 20
        factors.append(f"변동성 확대 구간({dr:+.1f}%)")
    elif dr >= 3:
        score += 10

    rsi = float(sar.rsi14 or 50)
    if rsi >= 85 or rsi <= 15:
        score += 20
        label = f"RSI 극단 과매수({rsi:.1f})" if rsi >= 85 else f"RSI 극단 과매도({rsi:.1f})"
        factors.append(label)
    elif rsi >= 80 or rsi <= 20:
        score += 12

    return min(100.0, score), factors


def _calc_overheating_risk(
    sar: Optional[StockAnalysisResult],
    cpar: Optional[ChartPatternAnalysisResult],
) -> tuple[float, list[str]]:
    """급등·거래량 과열 위험 (0-100)."""
    score = 0.0
    factors: list[str] = []

    if sar:
        rsi = float(sar.rsi14 or 50)
        if rsi >= 85:
            score += 50
            factors.append(f"RSI 극단 과매수({rsi:.1f})")
        elif rsi >= 80:
            score += 35
            factors.append(f"RSI 과매수 구간({rsi:.1f})")
        elif rsi >= 75:
            score += 20

        r5 = float(sar.return_5d or 0)
        if r5 >= 20:
            score += 40
            factors.append(f"단기 급등(+{r5:.1f}%, 5일)")
        elif r5 >= 15:
            score += 28
            factors.append(f"단기 과열 상승(+{r5:.1f}%, 5일)")
        elif r5 >= 10:
            score += 18
        elif r5 >= 5:
            score += 8

        vr5 = float(sar.volume_ratio_5d or 1)
        if vr5 >= 5:
            score += 30
            factors.append(f"거래량 과열({vr5:.1f}x, 5일 평균)")
        elif vr5 >= 3:
            score += 20
            factors.append(f"거래량 급증({vr5:.1f}x, 5일 평균)")
        elif vr5 >= 2:
            score += 10

    if cpar:
        if cpar.new_high_signal and sar and float(sar.return_5d or 0) >= 10:
            score += 15
            factors.append("신고가 근접 + 단기 강세")
        if cpar.volume_breakout_signal and sar and float(sar.return_5d or 0) >= 5:
            score = max(score, score + 10)

    return min(100.0, score), factors


def _calc_disclosure_risk(
    discs: list,
    disc_ai: Optional[DisclosureAIAnalysis],
) -> tuple[float, list[str]]:
    """공시 위험 (0-100)."""
    score = 0.0
    factors: list[str] = []

    if disc_ai:
        risk_label = disc_ai.ai_disclosure_risk or ""
        _MAP = {"주의": 80, "높음": 65, "보통": 35, "낮음": 10}
        score = _MAP.get(risk_label, 0)
        if risk_label in ("주의", "높음"):
            factors.append(f"공시 위험 등급: {risk_label}")

    # 최근 위험 공시 수 반영
    high_risk = [d for d in discs if (d.risk_level or "") in ("주의", "높음")]
    if high_risk:
        cnt = len(high_risk)
        score = max(score, 50 + min(cnt - 1, 3) * 10)
        factors.append(f"위험 공시 {cnt}건 (최근 30일)")
    elif discs and score < 15:
        score = max(score, 15)

    return min(100.0, score), factors


def _calc_sentiment_risk(
    nsr: Optional[NewsSentimentResult],
) -> tuple[float, list[str]]:
    """뉴스 악재 위험 (0-100)."""
    if not nsr:
        return 15.0, []

    factors: list[str] = []
    _MAP = {
        "강한 악재": 90,
        "악재 우세": 65,
        "중립":      20,
        "호재 우세":  5,
        "강한 호재":  0,
    }
    sig = nsr.news_sentiment_signal or ""
    score = float(_MAP.get(sig, 20))

    if sig in ("강한 악재", "악재 우세"):
        factors.append(f"뉴스 감성 {sig}")

    total = nsr.total_news_count or 0
    neg   = nsr.negative_news_count or 0
    if total > 0 and neg / total >= 0.5 and sig not in ("강한 악재", "악재 우세"):
        factors.append(f"악재 뉴스 비중 높음({neg}/{total}건)")
        score = max(score, 55)

    return min(100.0, score), factors


def _calc_financial_risk(
    far: Optional[FundamentalAnalysisResult],
) -> tuple[float, list[str]]:
    """실적 악화 위험 (0-100)."""
    if not far:
        return 20.0, []

    factors: list[str] = []
    _MAP = {
        "위험":    85,
        "주의":    60,
        "보통":    35,
        "우량":    10,
        "매우 우량": 0,
    }
    sig = far.fundamental_signal or "보통"
    score = float(_MAP.get(sig, 35))

    if sig in ("위험", "주의"):
        factors.append(f"펀더멘털 {sig} 등급")

    debt = float(far.debt_ratio or 0)
    if debt >= 300:
        score = max(score, 70)
        factors.append(f"부채비율 과다({debt:.0f}%)")
    elif debt >= 200:
        score = max(score, 55)
        factors.append(f"부채비율 높음({debt:.0f}%)")

    op_g = float(far.operating_income_growth or 0)
    if op_g <= -30:
        score = max(score, 65)
        factors.append(f"영업이익 급감({op_g:.1f}%)")
    elif op_g <= -10:
        score = max(score, 48)
        factors.append(f"영업이익 감소({op_g:.1f}%)")

    return min(100.0, score), factors


def _calc_supply_risk(
    sda: Optional[SupplyDemandAnalysis],
) -> tuple[float, list[str]]:
    """수급 불균형 위험 (0-100)."""
    if not sda:
        return 15.0, []

    score = 0.0
    factors: list[str] = []

    sr = float(sda.short_sell_ratio or 0)
    if sr >= 5:
        score += 50
        factors.append(f"공매도 비중 과대({sr:.1f}%)")
    elif sr >= 3:
        score += 35
        factors.append(f"공매도 비중 높음({sr:.1f}%)")
    elif sr >= 1:
        score += 15
        factors.append(f"공매도 비중 증가({sr:.1f}%)")

    f5 = float(sda.foreign_net_buy_5d or 0)
    i5 = float(sda.institution_net_buy_5d or 0)
    if f5 < 0 and i5 < 0:
        score += 30
        factors.append("외국인·기관 5일 동반 순매도")
    elif f5 < 0 and abs(f5) > abs(i5) * 2:
        score += 12

    sig = sda.supply_signal or ""
    if "매도우위" in sig:
        score = max(score, 40)
        if not any("매도" in f for f in factors):
            factors.append("수급 매도 우위")

    return min(100.0, score), factors


def _determine_risk_grade(total: float, overheating: float) -> str:
    # 과열이 심각하면 총점과 무관하게 과열주의
    if overheating >= 80:
        return "과열주의"
    if total >= 72:
        return "과열주의"
    if total >= 58:
        return "고위험"
    if total >= 38:
        return "주의"
    if total >= 18:
        return "보통"
    return "안정"


# ── 배치 데이터 로드 ──────────────────────────────────────────────

def _load_batch_data(
    session,
    stock_codes: list[str],
    analysis_date: date,
) -> dict:
    """여러 종목의 위험 분석 입력 데이터를 일괄 로드 (7개 테이블)."""
    codes = list(stock_codes)

    # 1. stock_analysis_results (당일, 중복 시 최신 우선)
    sar_rows = session.execute(
        select(StockAnalysisResult)
        .where(StockAnalysisResult.stock_code.in_(codes))
        .where(StockAnalysisResult.analysis_date == analysis_date)
        .order_by(StockAnalysisResult.id.desc())
    ).scalars().all()
    sar_map: dict[str, StockAnalysisResult] = {}
    for r in sar_rows:
        if r.stock_code not in sar_map:
            sar_map[r.stock_code] = r

    # 2. supply_demand_analysis_results (당일)
    sda_rows = session.execute(
        select(SupplyDemandAnalysis)
        .where(SupplyDemandAnalysis.stock_code.in_(codes))
        .where(SupplyDemandAnalysis.analysis_date == analysis_date)
    ).scalars().all()
    sda_map = {r.stock_code: r for r in sda_rows}

    # 3. news_sentiment_results (당일)
    nsr_rows = session.execute(
        select(NewsSentimentResult)
        .where(NewsSentimentResult.stock_code.in_(codes))
        .where(NewsSentimentResult.analysis_date == analysis_date)
    ).scalars().all()
    nsr_map = {r.stock_code: r for r in nsr_rows}

    # 4. fundamental_analysis_results (최신)
    far_rows = session.execute(
        select(FundamentalAnalysisResult)
        .where(FundamentalAnalysisResult.stock_code.in_(codes))
        .order_by(FundamentalAnalysisResult.analysis_date.desc(), FundamentalAnalysisResult.id.desc())
    ).scalars().all()
    far_map: dict[str, FundamentalAnalysisResult] = {}
    for r in far_rows:
        if r.stock_code not in far_map:
            far_map[r.stock_code] = r

    # 5. disclosures (최근 30일)
    disc_start = analysis_date - timedelta(days=30)
    disc_rows = session.execute(
        select(Disclosure)
        .where(Disclosure.stock_code.in_(codes))
        .where(Disclosure.report_date >= disc_start)
        .order_by(Disclosure.report_date.desc())
    ).scalars().all()
    disc_map: dict[str, list] = defaultdict(list)
    disc_id_map: dict[int, str] = {}   # disclosure_id → stock_code
    for r in disc_rows:
        disc_map[r.stock_code].append(r)
        disc_id_map[r.id] = r.stock_code

    # 6. disclosure_ai_analysis (위 공시 ID 기준, 종목별 최신)
    disc_ai_map: dict[str, DisclosureAIAnalysis] = {}
    if disc_id_map:
        ai_rows = session.execute(
            select(DisclosureAIAnalysis)
            .where(DisclosureAIAnalysis.disclosure_id.in_(list(disc_id_map.keys())))
            .order_by(DisclosureAIAnalysis.id.desc())
        ).scalars().all()
        for r in ai_rows:
            code = disc_id_map.get(r.disclosure_id) or r.stock_code
            if code and code not in disc_ai_map:
                disc_ai_map[code] = r

    # 7. chart_pattern_analysis_results (당일, 선택적)
    cpar_rows = session.execute(
        select(ChartPatternAnalysisResult)
        .where(ChartPatternAnalysisResult.stock_code.in_(codes))
        .where(ChartPatternAnalysisResult.analysis_date == analysis_date)
    ).scalars().all()
    cpar_map = {r.stock_code: r for r in cpar_rows}

    return {
        "sar":     sar_map,
        "sda":     sda_map,
        "nsr":     nsr_map,
        "far":     far_map,
        "disc":    disc_map,
        "disc_ai": disc_ai_map,
        "cpar":    cpar_map,
    }


# ── 단일 종목 점수 계산 ───────────────────────────────────────────

def _compute_risk(stock_code: str, data: dict) -> dict:
    """배치 데이터에서 단일 종목 위험 점수 산출."""
    sar     = data["sar"].get(stock_code)
    sda     = data["sda"].get(stock_code)
    nsr     = data["nsr"].get(stock_code)
    far     = data["far"].get(stock_code)
    discs   = data["disc"].get(stock_code, [])
    disc_ai = data["disc_ai"].get(stock_code)
    cpar    = data["cpar"].get(stock_code)

    all_factors: list[str] = []

    vol_r,   vf  = _calc_volatility_risk(sar)
    over_r,  of  = _calc_overheating_risk(sar, cpar)
    disc_r,  df  = _calc_disclosure_risk(discs, disc_ai)
    sent_r,  sf  = _calc_sentiment_risk(nsr)
    fin_r,   ff  = _calc_financial_risk(far)
    sup_r,   suf = _calc_supply_risk(sda)

    all_factors.extend(vf + of + df + sf + ff + suf)

    total = round(
        vol_r  * 0.20
        + over_r * 0.20
        + disc_r * 0.15
        + sent_r * 0.15
        + fin_r  * 0.15
        + sup_r  * 0.15,
        2,
    )
    grade = _determine_risk_grade(total, over_r)

    return {
        "volatility_risk":  round(vol_r,  2),
        "overheating_risk": round(over_r, 2),
        "disclosure_risk":  round(disc_r, 2),
        "sentiment_risk":   round(sent_r, 2),
        "financial_risk":   round(fin_r,  2),
        "supply_risk":      round(sup_r,  2),
        "total_risk_score": total,
        "risk_grade":       grade,
        "risk_factors":     json.dumps(all_factors, ensure_ascii=False),
    }


# ── AI 해설 ───────────────────────────────────────────────────────

def _sanitize(txt: Optional[str]) -> Optional[str]:
    if not txt:
        return txt
    for p in _BANNED:
        txt = txt.replace(p, "")
    return txt.strip() or None


def _call_risk_ai(
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

        factors = json.loads(metrics.get("risk_factors") or "[]")
        factors_text = "\n".join(f"  - {f}" for f in factors) if factors else "  (없음)"

        prompt = (
            f"[기준일: {target_date}] 분석 종목: {stock_name}({stock_code})\n\n"
            f"■ 위험 등급: {metrics['risk_grade']} "
            f"(종합 점수: {metrics['total_risk_score']:.1f}점)\n\n"
            f"■ 세부 위험 점수 (0=안전, 100=위험)\n"
            f"  변동성: {metrics['volatility_risk']:.0f} | "
            f"과열: {metrics['overheating_risk']:.0f} | "
            f"공시: {metrics['disclosure_risk']:.0f} | "
            f"뉴스: {metrics['sentiment_risk']:.0f} | "
            f"실적: {metrics['financial_risk']:.0f} | "
            f"수급: {metrics['supply_risk']:.0f}\n\n"
            f"■ 트리거된 위험 요인\n{factors_text}\n\n"
            "위 데이터를 바탕으로 JSON 형식의 위험도 해설을 작성하세요."
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
            "ai_risk_summary": _sanitize(raw.get("ai_risk_summary")),
            "ai_risk_factors": _sanitize(raw.get("ai_risk_factors")),
            "ai_risk_action":  _sanitize(raw.get("ai_risk_action")),
        }
    except Exception as e:
        logger.error(f"[위험분석AI] {stock_code} 오류: {e}")
        return {}


# ── DB 저장 ───────────────────────────────────────────────────────

def _upsert(session, stock_code: str, analysis_date: date, data: dict) -> None:
    fields = {k: v for k, v in data.items() if k not in ("stock_code", "analysis_date")}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(
        "INSERT INTO risk_analysis_results "
        "(stock_code, analysis_date, "
        + ", ".join(fields.keys())
        + ") VALUES (:stock_code, :analysis_date, "
        + ", ".join(f":{k}" for k in fields)
        + f") ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    session.execute(sql, {"stock_code": stock_code, "analysis_date": analysis_date, **fields})
    session.commit()


# ── 메인 분석 ────────────────────────────────────────────────────

def analyze_risk(
    stock_code: str,
    analysis_date: date,
    with_ai: bool = True,
) -> dict:
    """단일 종목 위험도 분석 → DB 저장."""
    session = get_db_session()
    try:
        stock = session.execute(
            select(Stock).where(Stock.stock_code == stock_code)
        ).scalar_one_or_none()
        stock_name = stock.stock_name if stock else stock_code

        data    = _load_batch_data(session, [stock_code], analysis_date)
        metrics = _compute_risk(stock_code, data)

        # AI는 주의 이상이거나 with_ai=True 일 때 호출
        if with_ai and metrics["total_risk_score"] >= 20:
            ai = _call_risk_ai(stock_code, stock_name, metrics, analysis_date)
            metrics.update(ai)

        _upsert(session, stock_code, analysis_date, metrics)

        logger.info(
            f"[위험분석] {stock_code} {stock_name} "
            f"등급={metrics['risk_grade']} 점수={metrics['total_risk_score']:.1f} "
            f"변동성={metrics['volatility_risk']:.0f} "
            f"과열={metrics['overheating_risk']:.0f} "
            f"수급={metrics['supply_risk']:.0f}"
        )
        return {
            "status": "success",
            "stock_code": stock_code,
            "stock_name": stock_name,
            **metrics,
        }
    except Exception as e:
        logger.error(f"[위험분석] {stock_code} 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "stock_code": stock_code, "message": str(e)}
    finally:
        session.close()


def run_risk_batch(
    analysis_date: Optional[date] = None,
    limit: int = 100,
    delay_sec: float = 0.05,
    with_ai: bool = True,
) -> dict:
    """관심종목 + 분석 상위 종목 위험도 배치 분석."""
    if analysis_date is None:
        analysis_date = date.today()

    session = get_db_session()
    try:
        from app.models.watchlist import WatchlistItem
        wl_codes = list(
            session.execute(
                select(WatchlistItem.stock_code)
            ).scalars().all()
        )
        top_codes = list(
            session.execute(
                select(StockAnalysisResult.stock_code)
                .where(StockAnalysisResult.analysis_date == analysis_date)
                .order_by(StockAnalysisResult.bullish_score.desc())
                .limit(limit)
            ).scalars().all()
        )
        targets = list(dict.fromkeys(wl_codes + top_codes))[:limit]
    finally:
        session.close()

    if not targets:
        return {"status": "no_data", "message": f"{analysis_date} 분석 대상 없음"}

    # 배치 데이터 로드 (한 번에)
    session2 = get_db_session()
    try:
        data = _load_batch_data(session2, targets, analysis_date)
        stock_rows = session2.execute(
            select(Stock.stock_code, Stock.stock_name).where(Stock.stock_code.in_(targets))
        ).all()
        name_map = {r.stock_code: r.stock_name for r in stock_rows}
    finally:
        session2.close()

    success = skipped = errors = 0
    for code in targets:
        try:
            metrics = _compute_risk(code, data)
            stock_name = name_map.get(code, code)

            if with_ai and metrics["total_risk_score"] >= 38:
                ai = _call_risk_ai(code, stock_name, metrics, analysis_date)
                metrics.update(ai)
                if delay_sec > 0:
                    time.sleep(delay_sec)

            sess = get_db_session()
            try:
                _upsert(sess, code, analysis_date, metrics)
            finally:
                sess.close()

            logger.debug(
                f"[위험분석] {code} 등급={metrics['risk_grade']} "
                f"점수={metrics['total_risk_score']:.1f}"
            )
            success += 1
        except Exception as e:
            logger.error(f"[위험분석] {code} 처리 오류: {e}")
            errors += 1

    return {
        "status": "success" if errors == 0 else "partial",
        "analysis_date": str(analysis_date),
        "total": len(targets),
        "success": success,
        "skipped": skipped,
        "errors": errors,
    }


# ── DB 읽기 ───────────────────────────────────────────────────────

def _row_to_dict(row: RiskAnalysisResult) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    try:
        factors = json.loads(row.risk_factors) if row.risk_factors else []
    except Exception:
        factors = []

    return {
        "stock_code":    row.stock_code,
        "analysis_date": str(row.analysis_date),
        "volatility_risk":  _f(row.volatility_risk),
        "overheating_risk": _f(row.overheating_risk),
        "disclosure_risk":  _f(row.disclosure_risk),
        "sentiment_risk":   _f(row.sentiment_risk),
        "financial_risk":   _f(row.financial_risk),
        "supply_risk":      _f(row.supply_risk),
        "total_risk_score": _f(row.total_risk_score),
        "risk_grade":       row.risk_grade or "보통",
        "risk_factors":     factors,
        "ai_risk_summary":  row.ai_risk_summary,
        "ai_risk_factors":  row.ai_risk_factors,
        "ai_risk_action":   row.ai_risk_action,
        "updated_at": str(row.updated_at) if row.updated_at else "-",
    }


def get_risk_result(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> Optional[dict]:
    session = get_db_session()
    try:
        q = select(RiskAnalysisResult).where(RiskAnalysisResult.stock_code == stock_code)
        if analysis_date:
            q = q.where(RiskAnalysisResult.analysis_date == analysis_date)
        q = q.order_by(RiskAnalysisResult.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_risk_top(
    analysis_date: Optional[date] = None,
    grade: Optional[str] = None,
    limit: int = 50,
    sort_by: str = "total",
) -> list[dict]:
    """
    위험 점수 상위 종목 조회.

    sort_by: total / volatility / overheating / disclosure / sentiment / financial / supply
    """
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(RiskAnalysisResult.analysis_date)
                .order_by(RiskAnalysisResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(RiskAnalysisResult).where(RiskAnalysisResult.analysis_date == analysis_date)
        if grade:
            q = q.where(RiskAnalysisResult.risk_grade == grade)

        _order_col = {
            "total":       RiskAnalysisResult.total_risk_score,
            "volatility":  RiskAnalysisResult.volatility_risk,
            "overheating": RiskAnalysisResult.overheating_risk,
            "disclosure":  RiskAnalysisResult.disclosure_risk,
            "sentiment":   RiskAnalysisResult.sentiment_risk,
            "financial":   RiskAnalysisResult.financial_risk,
            "supply":      RiskAnalysisResult.supply_risk,
        }.get(sort_by, RiskAnalysisResult.total_risk_score)

        q = q.order_by(_order_col.desc()).limit(limit)
        return [_row_to_dict(r) for r in session.execute(q).scalars().all()]
    finally:
        session.close()
