"""
기업 펀더멘털(실적) 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("")
def get_fundamental_top(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    signal: Optional[str] = Query(None, description="시그널 필터 (매우 우량/우량/보통/주의/위험)"),
    limit: int = Query(50, ge=1, le=200),
):
    """펀더멘털 점수 상위 종목 목록."""
    from app.services.fundamental_analysis_service import get_fundamental_top
    items = get_fundamental_top(analysis_date, limit=limit, signal=signal)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.get("/{stock_code}")
def get_fundamental_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """단일 종목 펀더멘털 분석 결과 조회."""
    from app.services.fundamental_analysis_service import get_fundamental
    result = get_fundamental(stock_code, analysis_date)
    if not result:
        return {"status": "not_found", "stock_code": stock_code}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.post("/analyze/{stock_code}")
def analyze_fundamental_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True),
):
    """단일 종목 펀더멘털 분석 실행."""
    from app.services.fundamental_analysis_service import analyze_fundamental
    target_date = analysis_date or date.today()
    result = analyze_fundamental(stock_code, target_date, with_ai=with_ai)
    return {**result, "disclaimer": DISCLAIMER}


@router.post("/batch")
def batch_fundamental_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(80, ge=1, le=200),
    background: bool = Query(True),
):
    """관심종목 + 상위 종목 펀더멘털 배치 분석."""
    from app.services.fundamental_analysis_service import run_fundamental_batch
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_fundamental_batch, target_date, limit)
        return {
            "status": "started",
            "message": f"{target_date} 펀더멘털 배치 분석 시작 (최대 {limit}종목)",
            "disclaimer": DISCLAIMER,
        }
    result = run_fundamental_batch(target_date, limit)
    return {**result, "disclaimer": DISCLAIMER}
