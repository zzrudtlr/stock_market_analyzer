"""
AI 기반 시장 리포트 생성 서비스
시장 데이터와 분석 결과를 기반으로 자연어 시장 요약 리포트를 생성합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 생성된 모든 문구는 참고용 분석 해설입니다.
"""
import json
import logging
from datetime import date
from typing import Optional

from sqlalchemy import func as sqlfunc, select

from app.config import settings
from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.disclosure import Disclosure
from app.models.market import MarketIndex
from app.models.market_report_ai import MarketReportAI
from app.models.stock import Stock
from app.models.watchlist import WatchlistGroup, WatchlistItem

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "본 리포트는 가격, 거래량, 추세 데이터를 기반으로 생성된 참고용 분석입니다. "
    "투자 판단은 사용자 본인 책임입니다."
)

BANNED_PHRASES = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승", "수익 보장",
    "지금 사야", "추천 종목", "무조건 상승", "확실한 수익", "투자 추천",
]

SYSTEM_PROMPT = """당신은 한국 주식 시장 데이터를 참고용으로 해설하는 분석 AI입니다.

[필수 준수 규칙]
1. 투자 추천, 매수·매도 권유 표현 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "강세 흐름 관찰", "변동성 확대 가능성", "거래량 증가 흐름", "시장 참고용 분석", "점검 필요"
4. 모든 문장은 중립적 데이터 해석 수준으로 작성
5. 한국어로 작성, 각 항목은 2~4문장으로 작성
6. 숫자 데이터를 적극 인용하여 구체적으로 서술

[출력 형식 - JSON만 반환, 다른 텍스트 없음]
{
  "market_ai_summary": "시장 전체 흐름 종합 요약 (2~3문장, 지수·강세·약세 비율 포함)",
  "bullish_market_comment": "강세 흐름 특징 해설 (2~3문장, 상위 종목·섹터 언급)",
  "bearish_market_comment": "약세 흐름 특징 해설 (2~3문장, 하락 요인 중립 서술)",
  "risk_market_comment": "주요 위험 요소 해설 (2~3문장, 공시·변동성·리스크 포함)",
  "volume_market_comment": "거래량 특징 해설 (2~3문장, 급증 종목 흐름 서술)"
}"""


# ── 데이터 수집 헬퍼 ─────────────────────────────────────────

def _get_indices(session, report_date: date) -> list[dict]:
    results = []
    for code, name in [("KS11", "KOSPI"), ("KQ11", "KOSDAQ")]:
        row = session.execute(
            select(MarketIndex)
            .where(MarketIndex.index_code == code, MarketIndex.trade_date <= report_date)
            .order_by(MarketIndex.trade_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row:
            results.append({
                "name":        name,
                "close_value": float(row.close_value) if row.close_value else None,
                "change_rate": float(row.change_rate) if row.change_rate else None,
            })
    return results


def _get_signal_summary(session, report_date: date) -> dict:
    """시그널별 종목 수 집계."""
    rows = session.execute(
        select(StockAnalysisResult.final_signal, sqlfunc.count().label("cnt"))
        .where(StockAnalysisResult.analysis_date == report_date)
        .group_by(StockAnalysisResult.final_signal)
    ).all()
    total = sum(r.cnt for r in rows)
    return {
        "total": total,
        "by_signal": {r.final_signal: r.cnt for r in rows if r.final_signal},
    }


def _get_top_stocks(session, report_date: date, kind: str, limit: int = 10) -> list[dict]:
    """강세/약세 상위 종목."""
    if kind == "bullish":
        order_col = StockAnalysisResult.bullish_score.desc()
        signal_filter = StockAnalysisResult.final_signal.in_(["강세 관심", "추세 유지"])
    else:
        order_col = StockAnalysisResult.bearish_score.desc()
        signal_filter = StockAnalysisResult.final_signal.in_(["약세 주의", "하락 위험"])

    rows = session.execute(
        select(StockAnalysisResult, Stock.stock_name)
        .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
        .where(StockAnalysisResult.analysis_date == report_date, signal_filter)
        .order_by(order_col)
        .limit(limit)
    ).all()

    result = []
    for ar, name in rows:
        result.append({
            "code":         ar.stock_code,
            "name":         name or ar.stock_code,
            "signal":       ar.final_signal or "-",
            "daily_return": float(ar.daily_return) if ar.daily_return else None,
            "return_5d":    float(ar.return_5d)    if ar.return_5d    else None,
            "bullish_score":float(ar.bullish_score) if ar.bullish_score else None,
            "bearish_score":float(ar.bearish_score) if ar.bearish_score else None,
            "volume_ratio": float(ar.volume_ratio_5d) if ar.volume_ratio_5d else None,
        })
    return result


def _get_high_volume(session, report_date: date, limit: int = 10) -> list[dict]:
    """거래량 급증 종목."""
    rows = session.execute(
        select(StockAnalysisResult, Stock.stock_name)
        .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
        .where(
            StockAnalysisResult.analysis_date == report_date,
            StockAnalysisResult.volume_ratio_5d >= 2.0,
        )
        .order_by(StockAnalysisResult.volume_ratio_5d.desc())
        .limit(limit)
    ).all()
    return [
        {
            "code":         ar.stock_code,
            "name":         name or ar.stock_code,
            "volume_ratio": float(ar.volume_ratio_5d) if ar.volume_ratio_5d else None,
            "daily_return": float(ar.daily_return)    if ar.daily_return    else None,
            "signal":       ar.final_signal or "-",
        }
        for ar, name in rows
    ]


def _get_disclosures(session, report_date: date, limit: int = 10) -> list[dict]:
    rows = session.execute(
        select(Disclosure, Stock.stock_name)
        .join(Stock, Disclosure.stock_code == Stock.stock_code, isouter=True)
        .where(Disclosure.report_date == report_date)
        .order_by(Disclosure.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "code":  d.stock_code or "-",
            "name":  name or "-",
            "title": d.title,
            "type":  d.disclosure_type or "-",
            "risk":  d.risk_level or "-",
        }
        for d, name in rows
    ]


def _get_watchlist_signals(session, report_date: date) -> dict:
    """관심종목 시그널 분포."""
    items = session.execute(
        select(WatchlistItem, StockAnalysisResult.final_signal)
        .join(
            StockAnalysisResult,
            (WatchlistItem.stock_code == StockAnalysisResult.stock_code)
            & (StockAnalysisResult.analysis_date == report_date),
            isouter=True,
        )
    ).all()
    total = len(items)
    bullish = sum(1 for _, sig in items if sig in ("강세 관심", "추세 유지"))
    bearish = sum(1 for _, sig in items if sig in ("약세 주의", "하락 위험"))
    return {"total": total, "bullish": bullish, "bearish": bearish}


# ── 프롬프트 빌더 ─────────────────────────────────────────────

def _build_prompt(data: dict) -> str:
    def f(v, fmt=".2f"): return format(float(v), fmt) if v is not None else "N/A"

    lines = ["[시장 데이터 요약]", f"기준일: {data['report_date']}", ""]

    # 지수
    lines.append("[시장 지수]")
    for idx in data.get("indices", []):
        cr = f(idx.get("change_rate"))
        cv = f(idx.get("close_value"), ",.2f")
        lines.append(f"{idx['name']}: {cv}p  등락률: {cr}%")
    lines.append("")

    # 시그널 요약
    sig = data.get("signal_summary", {})
    total = sig.get("total", 0)
    by_sig = sig.get("by_signal", {})
    lines.append("[종목 시그널 분포]")
    lines.append(f"전체 분석 종목: {total}개")
    for k, v in by_sig.items():
        pct = v / total * 100 if total else 0
        lines.append(f"  {k}: {v}개 ({pct:.1f}%)")
    lines.append("")

    # 강세 TOP10
    lines.append("[강세 종목 TOP10]")
    for s in data.get("bullish_top", [])[:10]:
        lines.append(
            f"  {s['code']} {s['name']} | 시그널:{s['signal']} | "
            f"당일:{f(s.get('daily_return'))}% | 5일:{f(s.get('return_5d'))}% | "
            f"강세점수:{f(s.get('bullish_score'),'.1f')}"
        )
    lines.append("")

    # 약세 TOP10
    lines.append("[약세 종목 TOP10]")
    for s in data.get("bearish_top", [])[:10]:
        lines.append(
            f"  {s['code']} {s['name']} | 시그널:{s['signal']} | "
            f"당일:{f(s.get('daily_return'))}% | 5일:{f(s.get('return_5d'))}% | "
            f"약세점수:{f(s.get('bearish_score'),'.1f')}"
        )
    lines.append("")

    # 거래량 급증
    lines.append("[거래량 급증 종목 TOP10]")
    for s in data.get("high_volume", [])[:10]:
        lines.append(
            f"  {s['code']} {s['name']} | "
            f"거래량비율:{f(s.get('volume_ratio'))}배 | "
            f"당일:{f(s.get('daily_return'))}% | 시그널:{s['signal']}"
        )
    lines.append("")

    # 공시
    discs = data.get("disclosures", [])
    lines.append(f"[오늘 공시 ({len(discs)}건)]")
    for d in discs[:10]:
        lines.append(f"  {d['code']} {d['name']} | {d['type']} | {d['title'][:40]}")
    lines.append("")

    # 관심종목
    wl = data.get("watchlist", {})
    lines.append("[관심종목 현황]")
    lines.append(
        f"  전체 {wl.get('total', 0)}개 | "
        f"강세 {wl.get('bullish', 0)}개 | "
        f"약세 {wl.get('bearish', 0)}개"
    )

    return "\n".join(lines)


# ── OpenAI 호출 ──────────────────────────────────────────────

def _is_configured() -> bool:
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def _call_openai(user_prompt: str) -> dict:
    import openai as _openai
    client = _openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1200,
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

    result = json.loads(response.choices[0].message.content)
    for phrase in BANNED_PHRASES:
        for key in result:
            if isinstance(result[key], str) and phrase in result[key]:
                logger.warning(f"[시장AI] 금지 표현 감지: '{phrase}'")
                result[key] = result[key].replace(phrase, "(참고용 분석 문구로 대체됨)")
    return result


# ── upsert ────────────────────────────────────────────────────

def _upsert(session, report_date: date, data: dict) -> None:
    rows = session.execute(
        select(MarketReportAI)
        .where(MarketReportAI.report_date == report_date)
        .order_by(MarketReportAI.id.desc())
    ).scalars().all()

    for extra in rows[1:]:
        session.delete(extra)

    row = rows[0] if rows else None
    if row is None:
        row = MarketReportAI(report_date=report_date)
        session.add(row)

    row.market_ai_summary      = data.get("market_ai_summary")
    row.bullish_market_comment = data.get("bullish_market_comment")
    row.bearish_market_comment = data.get("bearish_market_comment")
    row.risk_market_comment    = data.get("risk_market_comment")
    row.volume_market_comment  = data.get("volume_market_comment")


# ── 공개 API ──────────────────────────────────────────────────

def generate_market_report(report_date: Optional[date] = None) -> dict:
    """시장 데이터를 수집하고 AI 시장 리포트를 생성합니다."""
    if not _is_configured():
        return {"status": "error", "message": "OPENAI_API_KEY가 설정되지 않았습니다."}

    target_date = report_date or date.today()
    session = get_db_session()
    try:
        indices    = _get_indices(session, target_date)
        sig_summary = _get_signal_summary(session, target_date)

        if sig_summary.get("total", 0) == 0:
            return {"status": "error", "message": f"{target_date} 분석 데이터가 없습니다. 먼저 분석을 실행하세요."}

        bullish_top  = _get_top_stocks(session, target_date, "bullish", limit=10)
        bearish_top  = _get_top_stocks(session, target_date, "bearish", limit=10)
        high_volume  = _get_high_volume(session, target_date, limit=10)
        disclosures  = _get_disclosures(session, target_date, limit=10)
        watchlist    = _get_watchlist_signals(session, target_date)

        data = {
            "report_date":   str(target_date),
            "indices":       indices,
            "signal_summary": sig_summary,
            "bullish_top":   bullish_top,
            "bearish_top":   bearish_top,
            "high_volume":   high_volume,
            "disclosures":   disclosures,
            "watchlist":     watchlist,
        }

        prompt = _build_prompt(data)
        ai_result = _call_openai(prompt)

        _upsert(session, target_date, ai_result)
        session.commit()

        logger.info(f"[시장AI리포트] 생성 완료: {target_date}")
        return {
            "status":      "success",
            "report_date": str(target_date),
            "disclaimer":  DISCLAIMER,
            **ai_result,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"[시장AI리포트] 실패 ({target_date}): {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def get_market_report(report_date: Optional[date] = None) -> Optional[dict]:
    """저장된 AI 시장 리포트를 조회합니다."""
    target_date = report_date or date.today()
    session = get_db_session()
    try:
        row = session.execute(
            select(MarketReportAI)
            .where(MarketReportAI.report_date == target_date)
            .order_by(MarketReportAI.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not row:
            return None
        return {
            "report_date":          str(row.report_date),
            "market_ai_summary":    row.market_ai_summary,
            "bullish_market_comment": row.bullish_market_comment,
            "bearish_market_comment": row.bearish_market_comment,
            "risk_market_comment":  row.risk_market_comment,
            "volume_market_comment": row.volume_market_comment,
            "updated_at":           str(row.updated_at)[:19] if row.updated_at else "-",
            "disclaimer":           DISCLAIMER,
        }
    finally:
        session.close()
