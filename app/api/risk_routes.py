"""
종목 위험도 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("")
def get_risk_top(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    grade: Optional[str] = Query(
        None,
        description="등급 필터 (안정/보통/주의/고위험/과열주의)",
    ),
    sort_by: str = Query(
        "total",
        description="정렬 기준 (total/volatility/overheating/disclosure/sentiment/financial/supply)",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """위험 점수 상위 종목 목록."""
    from app.services.risk_analysis_service import get_risk_top
    items = get_risk_top(analysis_date, grade=grade, limit=limit, sort_by=sort_by)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.get("/{stock_code}")
def get_risk_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """단일 종목 위험도 분석 결과 조회."""
    from app.services.risk_analysis_service import get_risk_result
    result = get_risk_result(stock_code, analysis_date)
    if not result:
        return {"status": "not_found", "stock_code": stock_code}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.post("/analyze/{stock_code}")
def analyze_risk_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True),
):
    """단일 종목 위험도 분석 실행."""
    from app.services.risk_analysis_service import analyze_risk
    target_date = analysis_date or date.today()
    result = analyze_risk(stock_code, target_date, with_ai=with_ai)
    return {**result, "disclaimer": DISCLAIMER}


@router.post("/batch")
def batch_risk_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=300),
    with_ai: bool = Query(True),
    background: bool = Query(True),
):
    """관심종목 + 상위 종목 위험도 배치 분석."""
    from app.services.risk_analysis_service import run_risk_batch
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_risk_batch, target_date, limit, 0.05, with_ai)
        return {
            "status": "started",
            "message": f"{target_date} 위험도 배치 분석 시작 (최대 {limit}종목)",
            "disclaimer": DISCLAIMER,
        }
    result = run_risk_batch(target_date, limit, 0.05, with_ai)
    return {**result, "disclaimer": DISCLAIMER}
