"""
수급 분석 API — /api/supply-demand
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.supply_demand_analysis_service import (
    analyze_stock_supply_demand,
    get_supply_demand,
    get_supply_demand_top,
    run_supply_demand_batch,
)

router = APIRouter()


@router.get("")
def supply_demand_top(
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """수급 점수 상위 종목 목록 (당일 또는 지정일)."""
    target = analysis_date or date.today()
    rows = get_supply_demand_top(analysis_date=target, limit=limit)
    if not rows:
        return {
            "status": "not_found",
            "date": str(target),
            "message": "수급 분석 데이터가 없습니다. POST /api/supply-demand/batch 를 먼저 실행하세요.",
            "items": [],
        }
    return {"status": "ok", "date": str(target), "count": len(rows), "items": rows}


@router.get("/{stock_code}")
def supply_demand_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """특정 종목의 수급 분석 결과 조회."""
    target = analysis_date or date.today()
    data = get_supply_demand(stock_code, target)
    if not data:
        return {
            "status": "not_found",
            "stock_code": stock_code,
            "date": str(target),
            "message": "수급 분석 데이터 없음. POST /api/supply-demand/analyze/{stock_code} 실행 필요.",
        }
    return {"status": "ok", **data}


@router.post("/analyze/{stock_code}")
def supply_demand_analyze(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True, description="AI 해설 생성 여부"),
):
    """
    단일 종목 수급 분석 실행.
    참고용 수급 흐름 분석이며 투자 권유가 아닙니다.
    """
    target = analysis_date or date.today()
    return analyze_stock_supply_demand(stock_code, target, with_ai=with_ai)


@router.post("/batch")
def supply_demand_batch(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(80, ge=10, le=200),
    background: bool = Query(True),
):
    """
    관심종목 + 분석점수 상위 종목 수급 배치 분석.
    pykrx 요청 부하를 위해 종목당 약 0.3초 간격으로 실행됩니다.
    참고용 수급 흐름 분석이며 투자 권유가 아닙니다.
    """
    target = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_supply_demand_batch, target, limit)
        return {
            "status": "started",
            "date": str(target),
            "limit": limit,
            "message": f"수급 분석 배치를 백그라운드에서 실행합니다 (최대 {limit}개 종목).",
        }
    return run_supply_demand_batch(target, limit)
