"""
AI 기반 공시 분석 서비스
disclosures 테이블 데이터를 기반으로 공시 내용을 요약하고 위험도를 참고용으로 분석합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 생성된 모든 문구는 참고용 분석 해설입니다.
"""
import json
import logging
import time
from typing import Optional

from sqlalchemy import and_, select

from app.config import settings
from app.database import get_db_session
from app.models.disclosure import Disclosure
from app.models.disclosure_ai_analysis import DisclosureAIAnalysis

logger = logging.getLogger(__name__)

DISCLAIMER = "본 공시 분석은 참고용이며 투자 권유가 아닙니다."

VALID_RISK_LEVELS = {"낮음", "보통", "높음", "주의"}

BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승", "수익 보장",
    "지금 사야", "추천 종목", "무조건 상승", "확실한 수익", "투자 추천",
]

SYSTEM_PROMPT = """당신은 주식 공시 내용을 참고용으로 해설하는 분석 AI입니다.

[필수 준수 규칙]
1. 투자 추천, 매수·매도 권유 표현 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함", "추천 종목"
3. 허용 표현: "변동성 확대 가능성", "실적 기대감 반영 가능", "참고용 분석", "시장 관심 유입 가능성", "점검 필요"
4. 모든 문장은 중립적 데이터 해석 수준으로 작성
5. 한국어로 작성, 각 항목은 1~2문장으로 간결하게
6. ai_disclosure_risk는 반드시 아래 4개 값 중 하나만 사용: 낮음, 보통, 높음, 주의

[위험도 기준]
- 낮음: 정기 공시, 결산 보고, 임원 변경 등 일상적 공시
- 보통: 투자 계획, 계약 체결, 증자 검토 등 변화 가능성 공시
- 높음: 대규모 유상증자, 전환사채 발행, 소송 결과 등 직접 영향 공시
- 주의: 관리종목 지정, 불성실 공시, 감사의견 한정/거절 등 부정적 공시

[출력 형식 - JSON만 반환, 다른 텍스트 없음]
{
  "ai_disclosure_summary": "공시 내용을 중립적으로 요약 (1~2문장)",
  "ai_disclosure_risk": "낮음 또는 보통 또는 높음 또는 주의",
  "ai_market_impact": "시장 영향 참고 문구 (1~2문장, 중립적 가능성 서술)"
}"""


# ── 헬퍼 ─────────────────────────────────────────────────────

def _is_configured() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def _get_client():
    import openai
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def _sanitize(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        if phrase in text:
            logger.warning(f"[공시AI] 금지 표현 감지: '{phrase}'")
            text = text.replace(phrase, "(참고용 분석 문구로 대체됨)")
    return text


def _build_prompt(disclosure: dict) -> str:
    lines = [
        "[공시 정보]",
        f"종목코드: {disclosure.get('stock_code', 'N/A')}",
        f"공시 날짜: {disclosure.get('report_date', 'N/A')}",
        f"공시 유형: {disclosure.get('disclosure_type') or '일반'}",
        f"공시 제목: {disclosure.get('title', '')}",
    ]
    if disclosure.get("summary"):
        lines.append(f"공시 요약: {disclosure['summary']}")
    return "\n".join(lines)


def _call_openai(user_prompt: str) -> dict:
    import openai as _openai
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=400,
        )
    except _openai.AuthenticationError:
        raise RuntimeError("API 키가 유효하지 않습니다.")
    except _openai.RateLimitError as e:
        msg = str(e)
        if "insufficient_quota" in msg:
            raise RuntimeError("OpenAI 크레딧이 부족합니다.")
        raise RuntimeError(f"OpenAI 요청 한도 초과: {e}")
    except _openai.APIConnectionError:
        raise RuntimeError("OpenAI 서버 연결 실패.")
    except _openai.APIError as e:
        raise RuntimeError(f"OpenAI API 오류: {e}")

    content = response.choices[0].message.content
    result = json.loads(content)

    # 위험도 값 검증
    risk = result.get("ai_disclosure_risk", "보통")
    if risk not in VALID_RISK_LEVELS:
        result["ai_disclosure_risk"] = "보통"

    result["ai_disclosure_summary"] = _sanitize(result.get("ai_disclosure_summary"))
    result["ai_market_impact"]       = _sanitize(result.get("ai_market_impact"))
    return result


def _upsert(session, disclosure_id: int, stock_code: str, data: dict) -> None:
    rows = session.execute(
        select(DisclosureAIAnalysis).where(
            DisclosureAIAnalysis.disclosure_id == disclosure_id
        ).order_by(DisclosureAIAnalysis.id.desc())
    ).scalars().all()

    for extra in rows[1:]:
        session.delete(extra)

    row = rows[0] if rows else None
    if row is None:
        row = DisclosureAIAnalysis(
            disclosure_id=disclosure_id,
            stock_code=stock_code,
        )
        session.add(row)

    row.ai_disclosure_summary = data.get("ai_disclosure_summary")
    row.ai_disclosure_risk    = data.get("ai_disclosure_risk")
    row.ai_market_impact      = data.get("ai_market_impact")


# ── 공개 API ──────────────────────────────────────────────────

def analyze_disclosure_by_id(disclosure_id: int) -> dict:
    """단일 공시 ID에 대해 AI 분석을 실행하고 저장합니다."""
    if not _is_configured():
        return {"status": "error", "message": "OPENAI_API_KEY가 설정되지 않았습니다."}

    session = get_db_session()
    try:
        disc = session.execute(
            select(Disclosure).where(Disclosure.id == disclosure_id).limit(1)
        ).scalar_one_or_none()
        if not disc:
            return {"status": "error", "message": f"공시 ID {disclosure_id}를 찾을 수 없습니다."}

        disc_data = {
            "stock_code":      disc.stock_code,
            "report_date":     str(disc.report_date),
            "disclosure_type": disc.disclosure_type,
            "title":           disc.title,
            "summary":         disc.summary,
        }

        prompt = _build_prompt(disc_data)
        result = _call_openai(prompt)

        _upsert(session, disclosure_id, disc.stock_code or "", result)
        session.commit()

        logger.info(f"[공시AI] 완료: id={disclosure_id} / {disc.stock_code} / {disc.title[:30]}")
        return {
            "status":         "success",
            "disclosure_id":  disclosure_id,
            "stock_code":     disc.stock_code,
            "title":          disc.title,
            "disclaimer":     DISCLAIMER,
            **result,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"[공시AI] 실패 (id={disclosure_id}): {e}", exc_info=True)
        return {"status": "error", "disclosure_id": disclosure_id, "message": str(e)}
    finally:
        session.close()


def analyze_stock_disclosures(
    stock_code: str,
    limit: int = 5,
    skip_existing: bool = True,
) -> dict:
    """종목의 최근 공시에 대해 AI 분석을 일괄 실행합니다."""
    if not _is_configured():
        return {"status": "error", "message": "OPENAI_API_KEY가 설정되지 않았습니다."}

    session = get_db_session()
    try:
        disclosures = session.execute(
            select(Disclosure)
            .where(Disclosure.stock_code == stock_code)
            .order_by(Disclosure.report_date.desc(), Disclosure.id.desc())
            .limit(limit)
        ).scalars().all()
    finally:
        session.close()

    if not disclosures:
        return {"status": "error", "message": f"{stock_code} 공시 데이터가 없습니다."}

    processed, skipped, errors = [], [], []

    for disc in disclosures:
        if skip_existing:
            chk = get_db_session()
            try:
                exists = chk.execute(
                    select(DisclosureAIAnalysis.id)
                    .where(DisclosureAIAnalysis.disclosure_id == disc.id)
                    .limit(1)
                ).scalar_one_or_none()
            finally:
                chk.close()
            if exists:
                skipped.append(disc.id)
                continue

        result = analyze_disclosure_by_id(disc.id)
        if result.get("status") == "success":
            processed.append(disc.id)
        else:
            errors.append({"disclosure_id": disc.id, "error": result.get("message")})

        time.sleep(0.2)

    overall = "success" if not errors else ("partial" if processed else "error")
    logger.info(f"[공시AI배치] {stock_code} — 처리 {len(processed)}개, 스킵 {len(skipped)}개, 오류 {len(errors)}개")
    return {
        "status":    overall,
        "stock_code": stock_code,
        "processed": len(processed),
        "skipped":   len(skipped),
        "errors":    len(errors),
        "disclaimer": DISCLAIMER,
    }


def get_disclosure_analysis(stock_code: str, limit: int = 10) -> list:
    """종목의 저장된 공시 AI 분석 결과를 조회합니다."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(DisclosureAIAnalysis, Disclosure)
            .join(Disclosure, DisclosureAIAnalysis.disclosure_id == Disclosure.id)
            .where(DisclosureAIAnalysis.stock_code == stock_code)
            .order_by(Disclosure.report_date.desc(), DisclosureAIAnalysis.id.desc())
            .limit(limit)
        ).all()

        result = []
        for ai_row, disc in rows:
            result.append({
                "disclosure_id":        disc.id,
                "stock_code":           disc.stock_code,
                "report_date":          str(disc.report_date),
                "title":                disc.title,
                "disclosure_type":      disc.disclosure_type or "-",
                "ai_disclosure_summary": ai_row.ai_disclosure_summary,
                "ai_disclosure_risk":   ai_row.ai_disclosure_risk,
                "ai_market_impact":     ai_row.ai_market_impact,
                "updated_at":           str(ai_row.updated_at)[:19] if ai_row.updated_at else "-",
            })
        return result
    finally:
        session.close()
