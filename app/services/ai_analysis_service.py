"""
AI 기반 분석 해설 서비스
stock_analysis_results 정량 데이터를 기반으로 GPT-4o-mini 자연어 해설을 생성합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 생성된 모든 문구는 참고용 분석 해설입니다.
"""
import json
import logging
import re
import time
from datetime import date
from typing import Optional

from sqlalchemy import and_, select

from app.config import settings
from app.database import get_db_session
from app.models.ai_analysis import StockAIAnalysis
from app.models.analysis import StockAnalysisResult
from app.models.price import StockDailyPrice
from app.models.stock import Stock

logger = logging.getLogger(__name__)

DISCLAIMER = "본 내용은 기술적 지표 기반 참고용 분석이며 투자 권유가 아닙니다."

# GPT 응답에서 금지 표현 목록 (후처리 필터용)
BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승", "수익 보장",
    "지금 사야", "추천 종목", "무조건 상승", "확실한 수익",
]

SYSTEM_PROMPT = """당신은 주식 기술적 지표를 참고용으로 해설하는 분석 AI입니다.

[필수 준수 규칙]
1. 투자 추천, 매수·매도 권유 표현 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함", "추천 종목"
3. 허용 표현: "관심 흐름 관찰", "추세 강화 흐름", "변동성 확대 가능성", "거래량 증가 흐름", "참고용 분석", "위험 점검 필요"
4. 모든 문장은 데이터 해석 수준의 참고용 서술로 작성
5. 한국어로 작성, 각 항목은 1~3문장으로 간결하게

[출력 형식 - JSON만 반환, 다른 텍스트 없음]
{
  "ai_summary": "종합 요약: 현재 종목 상태를 중립적으로 서술 (1~2문장)",
  "ai_trend_comment": "이동평균선(MA5/MA20/MA60/MA120) 배열과 추세 흐름 해설 (1~2문장)",
  "ai_risk_comment": "변동성과 위험 점수 기반 리스크 수준 해설 (1~2문장)",
  "ai_volume_comment": "거래량 변화 흐름과 의미 해설 (1~2문장)",
  "ai_signal_comment": "최종 시그널과 기술적 지표 종합 해석 (1~2문장)"
}"""


# ── 헬퍼 ─────────────────────────────────────────────────────

def _is_configured() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def _get_client():
    import openai
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY)


def _fmt(v, fmt=".2f"):
    return format(float(v), fmt) if v is not None else "N/A"


def _build_user_prompt(data: dict) -> str:
    """분석 데이터를 구조화된 프롬프트로 변환."""
    def f(v, spec=".2f"): return format(float(v), spec) if v is not None else "N/A"

    lines = [
        f"[종목 기본 정보]",
        f"종목명: {data.get('stock_name', '알 수 없음')} ({data.get('stock_code', '')})",
        f"시장: {data.get('market', 'N/A')}",
        f"최근 종가: {int(data['close_price']):,}원" if data.get('close_price') else "최근 종가: N/A",
        "",
        "[수익률 데이터]",
        f"당일 등락률: {f(data.get('daily_return'))}%",
        f"5일 수익률: {f(data.get('return_5d'))}%",
        f"20일 수익률: {f(data.get('return_20d'))}%",
        f"60일 수익률: {f(data.get('return_60d'))}%",
        "",
        "[이동평균선 (원)]",
        f"MA5: {f(data.get('ma5'), ',.0f')}",
        f"MA20: {f(data.get('ma20'), ',.0f')}",
        f"MA60: {f(data.get('ma60'), ',.0f')}",
        f"MA120: {f(data.get('ma120'), ',.0f')}",
        "",
        "[거래량 지표]",
        f"거래량비율(5일 평균 대비): {f(data.get('volume_ratio_5d'))}배",
        f"거래량비율(20일 평균 대비): {f(data.get('volume_ratio_20d'))}배",
        "",
        "[기술 지표]",
        f"RSI14: {f(data.get('rsi14'))}",
        f"변동성(20일): {f(data.get('volatility_20d'))}%",
        f"시장 대비 상대강도(KOSPI): {f(data.get('relative_strength'))}%p",
        "",
        "[분석 점수 (0~30 척도)]",
        f"모멘텀점수: {f(data.get('momentum_score'), '.1f')}",
        f"거래량점수: {f(data.get('volume_score'), '.1f')}",
        f"추세점수: {f(data.get('trend_score'), '.1f')}",
        f"위험점수: {f(data.get('risk_score'), '.1f')}",
        f"강세점수: {f(data.get('bullish_score'), '.1f')}",
        f"약세점수: {f(data.get('bearish_score'), '.1f')}",
        "",
        "[최종 시그널]",
        f"시그널: {data.get('final_signal', 'N/A')}",
        f"시그널 사유: {data.get('signal_reason', 'N/A')}",
    ]
    return "\n".join(lines)


def _call_openai(user_prompt: str) -> dict:
    """OpenAI API 호출 및 JSON 파싱."""
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
            temperature=0.3,
            max_tokens=800,
        )
    except _openai.AuthenticationError:
        raise RuntimeError("API 키가 유효하지 않습니다. .env의 OPENAI_API_KEY를 확인하세요.")
    except _openai.RateLimitError as e:
        msg = str(e)
        if "insufficient_quota" in msg:
            raise RuntimeError(
                "OpenAI 크레딧이 부족합니다. "
                "https://platform.openai.com/account/billing 에서 결제 정보를 확인하세요."
            )
        raise RuntimeError(f"OpenAI 요청 한도 초과 (잠시 후 재시도): {e}")
    except _openai.APIConnectionError:
        raise RuntimeError("OpenAI 서버 연결 실패. 네트워크를 확인하세요.")
    except _openai.APIError as e:
        raise RuntimeError(f"OpenAI API 오류: {e}")

    content = response.choices[0].message.content
    return json.loads(content)


def _sanitize(text: Optional[str]) -> Optional[str]:
    """금지 표현 후처리 필터."""
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        if phrase in text:
            logger.warning(f"[AI분석] 금지 표현 감지 및 제거: '{phrase}'")
            text = text.replace(phrase, "(참고용 분석 문구로 대체됨)")
    return text


def _sanitize_result(result: dict) -> dict:
    return {k: _sanitize(v) for k, v in result.items()}


def _upsert_ai_analysis(session, stock_code: str, analysis_date: date, data: dict) -> None:
    """stock_ai_analysis 테이블 upsert (stock_code + analysis_date 기준)."""
    # 중복 행이 있을 수 있으므로 최신 1건만 취하고 나머지 삭제
    rows = session.execute(
        select(StockAIAnalysis).where(
            and_(
                StockAIAnalysis.stock_code    == stock_code,
                StockAIAnalysis.analysis_date == analysis_date,
            )
        ).order_by(StockAIAnalysis.id.desc())
    ).scalars().all()

    for extra in rows[1:]:
        session.delete(extra)

    row = rows[0] if rows else None

    if row is None:
        row = StockAIAnalysis(
            stock_code=stock_code,
            analysis_date=analysis_date,
        )
        session.add(row)

    row.ai_summary        = data.get("ai_summary")
    row.ai_trend_comment  = data.get("ai_trend_comment")
    row.ai_risk_comment   = data.get("ai_risk_comment")
    row.ai_volume_comment = data.get("ai_volume_comment")
    row.ai_signal_comment = data.get("ai_signal_comment")


def _fetch_stock_data(session, stock_code: str, analysis_date: date) -> Optional[dict]:
    """DB에서 종목 분석 데이터 조회."""
    ar = session.execute(
        select(StockAnalysisResult).where(
            and_(
                StockAnalysisResult.stock_code    == stock_code,
                StockAnalysisResult.analysis_date == analysis_date,
            )
        ).order_by(StockAnalysisResult.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not ar:
        return None

    stock = session.execute(
        select(Stock).where(Stock.stock_code == stock_code).limit(1)
    ).scalar_one_or_none()

    price = session.execute(
        select(StockDailyPrice)
        .where(StockDailyPrice.stock_code == stock_code)
        .order_by(StockDailyPrice.trade_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    def _f(v): return float(v) if v is not None else None

    return {
        "stock_code":       stock_code,
        "stock_name":       stock.stock_name if stock else stock_code,
        "market":           stock.market     if stock else "N/A",
        "close_price":      price.close_price if price else None,
        "volume":           price.volume      if price else None,
        "daily_return":     _f(ar.daily_return),
        "return_5d":        _f(ar.return_5d),
        "return_20d":       _f(ar.return_20d),
        "return_60d":       _f(ar.return_60d),
        "volume_ratio_5d":  _f(ar.volume_ratio_5d),
        "volume_ratio_20d": _f(ar.volume_ratio_20d),
        "ma5":              _f(ar.ma5),
        "ma20":             _f(ar.ma20),
        "ma60":             _f(ar.ma60),
        "ma120":            _f(ar.ma120),
        "rsi14":            _f(ar.rsi14),
        "volatility_20d":   _f(ar.volatility_20d),
        "relative_strength":_f(ar.relative_strength),
        "momentum_score":   _f(ar.momentum_score),
        "volume_score":     _f(ar.volume_score),
        "trend_score":      _f(ar.trend_score),
        "risk_score":       _f(ar.risk_score),
        "bullish_score":    _f(ar.bullish_score),
        "bearish_score":    _f(ar.bearish_score),
        "final_signal":     ar.final_signal,
        "signal_reason":    ar.signal_reason,
    }


# ── 공개 API ──────────────────────────────────────────────────

def analyze_stock(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> dict:
    """
    단일 종목 AI 분석 해설 생성 및 DB 저장.
    기존 분석이 있으면 덮어씁니다.
    """
    if not _is_configured():
        return {"status": "error", "message": "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."}

    target_date = analysis_date or date.today()
    session = get_db_session()

    try:
        data = _fetch_stock_data(session, stock_code, target_date)
        if not data:
            return {
                "status": "error",
                "message": f"{stock_code} / {target_date} 분석 데이터가 없습니다. 먼저 분석을 실행하세요.",
            }

        user_prompt = _build_user_prompt(data)
        ai_raw      = _call_openai(user_prompt)
        ai_result   = _sanitize_result(ai_raw)

        _upsert_ai_analysis(session, stock_code, target_date, ai_result)
        session.commit()

        logger.info(f"[AI분석] 완료: {stock_code} / {target_date}")
        return {
            "status":       "success",
            "stock_code":   stock_code,
            "stock_name":   data.get("stock_name"),
            "analysis_date": str(target_date),
            "disclaimer":   DISCLAIMER,
            **ai_result,
        }

    except Exception as e:
        session.rollback()
        logger.error(f"[AI분석] 실패 ({stock_code}): {e}", exc_info=True)
        return {"status": "error", "stock_code": stock_code, "message": str(e)}

    finally:
        session.close()


def analyze_daily_batch(
    analysis_date: Optional[date] = None,
    limit: int = 30,
    skip_existing: bool = True,
) -> dict:
    """
    오늘 분석 결과 기준 상위 종목들에 대해 AI 해설을 일괄 생성합니다.
    limit: 처리할 최대 종목 수 (비용 제어, 기본 30)
    skip_existing: True이면 이미 AI 분석이 있는 종목 건너뜀
    """
    if not _is_configured():
        return {"status": "error", "message": "OPENAI_API_KEY가 설정되지 않았습니다."}

    target_date = analysis_date or date.today()
    session = get_db_session()

    try:
        # 강세점수 높은 순 + 절대 등락률 높은 순으로 대상 추출
        candidates = session.execute(
            select(StockAnalysisResult.stock_code)
            .where(StockAnalysisResult.analysis_date == target_date)
            .order_by(
                StockAnalysisResult.bullish_score.desc(),
                StockAnalysisResult.momentum_score.desc(),
            )
            .limit(limit * 3)   # skip_existing 감안해서 여유 있게 조회
        ).scalars().all()

    finally:
        session.close()

    if not candidates:
        return {"status": "error", "message": f"{target_date} 분석 데이터가 없습니다."}

    processed = []
    skipped   = []
    errors    = []

    for stock_code in candidates:
        if len(processed) >= limit:
            break

        # 이미 분석 있으면 건너뜀
        if skip_existing:
            chk_session = get_db_session()
            try:
                exists = chk_session.execute(
                    select(StockAIAnalysis.id).where(
                        and_(
                            StockAIAnalysis.stock_code    == stock_code,
                            StockAIAnalysis.analysis_date == target_date,
                        )
                    ).limit(1)
                ).scalar_one_or_none()
            finally:
                chk_session.close()

            if exists:
                skipped.append(stock_code)
                continue

        result = analyze_stock(stock_code, target_date)
        if result.get("status") == "success":
            processed.append(stock_code)
        else:
            errors.append({"stock_code": stock_code, "error": result.get("message")})
            logger.warning(f"[AI배치] {stock_code} 실패: {result.get('message')}")

        time.sleep(0.3)   # rate limit 여유

    overall = "success" if not errors else ("partial" if processed else "error")
    logger.info(
        f"[AI배치] 완료 — 처리 {len(processed)}개, 스킵 {len(skipped)}개, 오류 {len(errors)}개"
    )
    return {
        "status":       overall,
        "date":         str(target_date),
        "processed":    len(processed),
        "skipped":      len(skipped),
        "errors":       len(errors),
        "error_details": errors[:10],
        "disclaimer":   DISCLAIMER,
    }


def get_ai_analysis(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> Optional[dict]:
    """DB에서 AI 분석 결과 조회."""
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        row = session.execute(
            select(StockAIAnalysis).where(
                and_(
                    StockAIAnalysis.stock_code    == stock_code,
                    StockAIAnalysis.analysis_date == target_date,
                )
            ).order_by(StockAIAnalysis.id.desc()).limit(1)
        ).scalar_one_or_none()

        if not row:
            return None

        return {
            "stock_code":       row.stock_code,
            "analysis_date":    str(row.analysis_date),
            "ai_summary":       row.ai_summary,
            "ai_trend_comment": row.ai_trend_comment,
            "ai_risk_comment":  row.ai_risk_comment,
            "ai_volume_comment":row.ai_volume_comment,
            "ai_signal_comment":row.ai_signal_comment,
            "created_at":       str(row.created_at)[:19] if row.created_at else None,
            "updated_at":       str(row.updated_at)[:19] if row.updated_at else None,
            "disclaimer":       DISCLAIMER,
        }
    finally:
        session.close()
