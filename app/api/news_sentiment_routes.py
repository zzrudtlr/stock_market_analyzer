"""
뉴스 감성 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("")
def get_news_top(
    analysis_date: Optional[date] = Query(None, description="분석 기준일 (기본: 최신)"),
    signal: Optional[str] = Query(None, description="시그널 필터 (강한 호재/호재 우세/중립/악재 우세/강한 악재)"),
    limit: int = Query(50, ge=1, le=200),
):
    """뉴스 감성 점수 상위 종목 목록."""
    from app.services.news_analysis_service import get_news_sentiment_top
    items = get_news_sentiment_top(analysis_date, limit=limit, signal=signal)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.get("/{stock_code}")
def get_news_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """단일 종목 뉴스 감성 결과 조회."""
    from app.services.news_analysis_service import get_news_sentiment
    result = get_news_sentiment(stock_code, analysis_date)
    if not result:
        return {"status": "not_found", "stock_code": stock_code}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.post("/analyze/{stock_code}")
def analyze_news_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True),
):
    """단일 종목 뉴스 감성 분석 실행."""
    from app.services.news_analysis_service import analyze_news_sentiment
    target_date = analysis_date or date.today()
    result = analyze_news_sentiment(stock_code, target_date, with_ai=with_ai)
    return {**result, "disclaimer": DISCLAIMER}


@router.post("/batch")
def batch_news_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(80, ge=1, le=200),
    background: bool = Query(True),
):
    """관심종목 + 상위 종목 뉴스 감성 배치 분석."""
    from app.services.news_analysis_service import run_news_batch
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_news_batch, target_date, limit)
        return {
            "status": "started",
            "message": f"{target_date} 뉴스 감성 배치 분석을 백그라운드로 시작합니다 (최대 {limit}종목)",
            "disclaimer": DISCLAIMER,
        }
    result = run_news_batch(target_date, limit)
    return {**result, "disclaimer": DISCLAIMER}
