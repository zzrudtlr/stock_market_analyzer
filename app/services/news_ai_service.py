"""
뉴스 감성 AI 분류 서비스

수집된 헤드라인을 GPT-4o-mini로 호재/악재/중립 분류하고
시장 심리 해설을 생성합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 모든 결과는 참고용 뉴스 감성 분석 정보입니다.
"""
import json
import logging
from datetime import date
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

_SYSTEM_PROMPT = """당신은 한국 주식 시장 뉴스 감성 분석 전문가입니다.

[역할]
뉴스 헤드라인의 기업·시장 영향을 호재/악재/중립으로 분류하고
시장 심리 흐름을 해설합니다.

[분류 기준]
- 호재: 실적 개선·서프라이즈, 수주·계약 성사, 신제품·기술 개발, 배당 확대,
        외국인·기관 매수, 정부 지원·규제 완화, 목표주가 상향, 긍정 업황
- 악재: 실적 악화·쇼크, 계약 해지·취소, 소송·제재·벌금, 규제 강화,
        대규모 유상증자, 핵심 인력 이탈, 부정 업황, 목표주가 하향
- 중립: 단순 가격 변동 보도, 양면적 내용, 사실 확인 불가, 일반 현황 보도

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "감성 관찰", "흐름 확인", "이슈 주목", "변동성 확대 가능성"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "classifications": [
    {
      "title": "헤드라인 그대로",
      "sentiment": "호재",
      "reason": "분류 이유 1문장"
    }
  ],
  "ai_sentiment_summary": "전반적 감성 흐름 1~2문장 (호재/악재 비율 + 핵심 이슈)",
  "ai_key_issues": "주요 이슈 키워드 나열 1~2문장 (수주/실적/정책 등)",
  "ai_sentiment_risk": "뉴스 기반 주의사항 1~2문장 (악재 집중 또는 변동성 요인)"
}"""


def _sanitize(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        text = text.replace(phrase, "")
    return text.strip() or None


def classify_news_sentiment(
    headlines: list[dict],
    stock_name: str,
    analysis_date: date,
) -> dict:
    """
    헤드라인 목록을 GPT-4o-mini로 일괄 감성 분류.

    Args:
        headlines: [{"title": "...", "source": "google|naver|dart"}]
        stock_name: 종목명 (컨텍스트 제공용)
        analysis_date: 분석 기준일

    Returns:
        {
          "classifications": [{title, sentiment, reason}],
          "ai_sentiment_summary": ...,
          "ai_key_issues": ...,
          "ai_sentiment_risk": ...,
        }
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[뉴스AI] OPENAI_API_KEY 미설정 — AI 감성 분류 생략")
        return {}

    if not headlines:
        return {}

    import openai
    client = openai.OpenAI(api_key=api_key)

    # 헤드라인을 20개씩 배치 처리 (JSON 잘림 방지)
    all_classifications: list[dict] = []
    ai_fields: dict = {}
    batch_size = 20

    for batch_idx in range(0, len(headlines), batch_size):
        batch = headlines[batch_idx: batch_idx + batch_size]
        is_last = (batch_idx + batch_size) >= len(headlines)

        headline_text = "\n".join(
            f"{i+1}. [{h.get('source','?')}] {h['title']}"
            for i, h in enumerate(batch)
        )
        prompt = (
            f"[기준일: {analysis_date}] 분석 대상 종목: {stock_name}\n\n"
            f"다음 뉴스 헤드라인들을 감성 분류하세요:\n\n{headline_text}\n\n"
            + ("위 헤드라인 분류와 함께 ai_sentiment_summary, ai_key_issues, "
               "ai_sentiment_risk 도 작성하세요." if is_last else
               "이 배치만 classifications 배열에 분류하세요. "
               "ai_sentiment_summary 등 요약 필드는 비워도 됩니다.")
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000,
            )
            raw = json.loads(resp.choices[0].message.content)
            all_classifications.extend(raw.get("classifications", []))
            if is_last:
                ai_fields = {
                    "ai_sentiment_summary": _sanitize(raw.get("ai_sentiment_summary")),
                    "ai_key_issues":        _sanitize(raw.get("ai_key_issues")),
                    "ai_sentiment_risk":    _sanitize(raw.get("ai_sentiment_risk")),
                }
        except Exception as e:
            logger.error(f"[뉴스AI] 배치 {batch_idx//batch_size + 1} 실패: {e}")

    return {"classifications": all_classifications, **ai_fields}
