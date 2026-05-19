"""
테마 AI 해설 서비스

테마 집계 통계 + 뉴스 헤드라인을 GPT-4o-mini에 보내
5개 필드(summary / risk / flow / volume_comment / rotation_comment)를 생성합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 모든 결과는 참고용 시장 흐름 정보입니다.
"""
import json
import logging
from datetime import date
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승", "수익 보장",
    "지금 사야", "추천 종목", "무조건 상승", "확실한 수익", "급등 예상",
]

SYSTEM_PROMPT = """당신은 한국 주식시장의 테마별 흐름을 분석하는 참고용 AI 시장 해설가입니다.

[역할]
- 정량 지표(수익률, 거래량비율, 점수) + 실시간 뉴스 헤드라인을 종합하여
  테마가 왜 강세/약세인지 맥락 있는 해설을 제공합니다.
- 정책 변화, 기업 이슈, 글로벌 변수, 수급 변화 등 배경을 설명합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함", "급등 예상"
3. 허용 표현: "강세 흐름 관찰", "상승 압력 존재", "약세 흐름 관찰", "변동성 확대", "뉴스 주목"
4. 뉴스가 없으면 지표 기반으로만 서술, 없는 정보 지어내기 금지
5. 각 필드는 간결하게 1~2문장 이내로 작성
6. 한국어로만 작성

[출력 형식 — JSON 배열만 반환, 다른 텍스트 없음]
[
  {
    "theme_name": "테마명",
    "ai_theme_summary": "테마 현황 1~2문장 요약 (시그널 + 핵심 지표)",
    "ai_theme_risk": "리스크 및 주의사항 1~2문장",
    "ai_theme_flow": "자금 흐름 및 수급 특징 1~2문장",
    "ai_theme_volume_comment": "거래량 특이 사항 1문장",
    "ai_theme_rotation_comment": "순환매 가능성 1문장"
  }
]"""


def _sanitize(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        text = text.replace(phrase, "")
    return text.strip() or None


def _build_prompt(theme_stats: list[dict], target_date: date,
                  news_map: dict[str, list[str]]) -> str:
    lines = [
        f"[기준일: {target_date}]",
        "아래는 한국 주식시장 테마별 분석 통계와 관련 뉴스 헤드라인입니다.\n",
    ]
    for t in theme_stats:
        s = t["stats"]
        news = news_map.get(t["theme_name"], [])
        news_block = (
            "  관련뉴스:\n" + "\n".join(f"    · {h}" for h in news)
            if news else "  관련뉴스: 수집 없음"
        )
        strongest = t.get("spotlight", {}).get("strongest", {})
        weakest   = t.get("spotlight", {}).get("weakest", {})
        lines.append(
            f"▶ 테마: {t['theme_name']}  (시그널: {s['theme_signal']})\n"
            f"  종목수: {s['stock_count']}개\n"
            f"  당일등락: {s['avg_return_1d']:+.2f}%"
            f"  | 5일: {s['avg_return_5d']:+.2f}%"
            f"  | 20일: {s['avg_return_20d']:+.2f}%\n"
            f"  거래량비율(5일): {s['avg_volume_ratio']:.2f}x"
            f"  | 강세비율: {s['bullish_ratio']:.0f}%"
            f"  | 약세비율: {s['bearish_ratio']:.0f}%\n"
            f"  모멘텀점수: {s['momentum_avg']:.1f}"
            f"  | 추세점수: {s['trend_avg']:.1f}"
            f"  | 위험점수: {s['risk_avg']:.1f}\n"
            + (f"  강세대표: {strongest.get('name','')}({strongest.get('return_5d',0):+.1f}%)\n"
               if strongest else "")
            + (f"  약세대표: {weakest.get('name','')}({weakest.get('return_5d',0):+.1f}%)\n"
               if weakest else "")
            + news_block
        )
    lines.append("\n위 데이터를 바탕으로 JSON 배열로 각 테마 분석을 작성하세요.")
    return "\n\n".join(lines)


def _call_single_batch(client, theme_batch: list[dict], target_date: date,
                       news_map: dict[str, list[str]]) -> dict[str, dict]:
    prompt = _build_prompt(theme_batch, target_date, news_map)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=4000,
    )
    raw = json.loads(resp.choices[0].message.content)
    if isinstance(raw, list):
        items = raw
    else:
        items = next((v for v in raw.values() if isinstance(v, list)), [])
    return {
        item["theme_name"]: {
            "ai_theme_summary":          _sanitize(item.get("ai_theme_summary")),
            "ai_theme_risk":             _sanitize(item.get("ai_theme_risk")),
            "ai_theme_flow":             _sanitize(item.get("ai_theme_flow")),
            "ai_theme_volume_comment":   _sanitize(item.get("ai_theme_volume_comment")),
            "ai_theme_rotation_comment": _sanitize(item.get("ai_theme_rotation_comment")),
        }
        for item in items
        if "theme_name" in item
    }


def call_theme_ai(theme_stats: list[dict], target_date: date,
                  news_map: dict[str, list[str]]) -> dict[str, dict]:
    """
    테마 목록을 10개씩 배치로 나눠 GPT-4o-mini에 요청 (JSON 잘림 방지).
    반환: {theme_name: {ai_theme_summary, ai_theme_risk, ai_theme_flow,
                        ai_theme_volume_comment, ai_theme_rotation_comment}}
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[테마AI] OPENAI_API_KEY 미설정 — AI 해설 생략")
        return {}

    import openai
    client = openai.OpenAI(api_key=api_key)
    result: dict[str, dict] = {}
    batch_size = 10

    for i in range(0, len(theme_stats), batch_size):
        batch = theme_stats[i:i + batch_size]
        batch_names = [t["theme_name"] for t in batch]
        logger.info(f"[테마AI] 배치 {i//batch_size + 1} 요청 — {batch_names}")
        try:
            batch_result = _call_single_batch(client, batch, target_date, news_map)
            result.update(batch_result)
            logger.info(f"[테마AI] 배치 {i//batch_size + 1} 완료 — {len(batch_result)}개")
        except Exception as e:
            logger.error(f"[테마AI] 배치 {i//batch_size + 1} 실패: {e}")

    return result
