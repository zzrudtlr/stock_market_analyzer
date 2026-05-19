"""
차트 패턴 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("")
def get_chart_pattern_top(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    signal: Optional[str] = Query(None, description="시그널 필터 (강한상승패턴/상승패턴/중립/약세/하락주의)"),
    pattern: Optional[str] = Query(None, description="패턴 필터 (golden_cross/breakout/new_high/volume/pullback)"),
    limit: int = Query(50, ge=1, le=200),
):
    """차트 패턴 점수 상위 종목 목록."""
    from app.services.chart_pattern_analysis_service import get_chart_pattern_top
    items = get_chart_pattern_top(analysis_date, limit=limit, signal=signal, pattern=pattern)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.get("/{stock_code}")
def get_chart_pattern_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """단일 종목 차트 패턴 분석 결과 조회."""
    from app.services.chart_pattern_analysis_service import get_chart_pattern
    result = get_chart_pattern(stock_code, analysis_date)
    if not result:
        return {"status": "not_found", "stock_code": stock_code}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.post("/analyze/{stock_code}")
def analyze_chart_pattern_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True),
):
    """단일 종목 차트 패턴 분석 실행."""
    from app.services.chart_pattern_analysis_service import analyze_chart_pattern
    target_date = analysis_date or date.today()
    result = analyze_chart_pattern(stock_code, target_date, with_ai=with_ai)
    return {**result, "disclaimer": DISCLAIMER}


@router.post("/batch")
def batch_chart_pattern_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=300),
    background: bool = Query(True),
):
    """관심종목 + 상위 종목 차트 패턴 배치 분석."""
    from app.services.chart_pattern_analysis_service import run_chart_pattern_batch
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_chart_pattern_batch, target_date, limit)
        return {
            "status": "started",
            "message": f"{target_date} 차트 패턴 배치 분석 시작 (최대 {limit}종목)",
            "disclaimer": DISCLAIMER,
        }
    result = run_chart_pattern_batch(target_date, limit)
    return {**result, "disclaimer": DISCLAIMER}
