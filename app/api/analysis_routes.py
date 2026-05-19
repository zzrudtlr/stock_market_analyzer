from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.analysis_service import get_analysis_results, get_analysis_summary, run_analysis

router = APIRouter()


@router.get("/summary")
def analysis_summary(analysis_date: Optional[date] = Query(None)):
    return get_analysis_summary(analysis_date)


@router.get("/bullish")
def bullish_stocks(
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(20, le=100),
):
    return get_analysis_results(analysis_date, order_by="bullish_score", limit=limit)


@router.get("/bearish")
def bearish_stocks(
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(20, le=100),
):
    return get_analysis_results(analysis_date, order_by="bearish_score", limit=limit)


@router.post("/run")
def trigger_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    market: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    background: bool = Query(False),
):
    if background:
        background_tasks.add_task(run_analysis, analysis_date, market, limit)
        return {"status": "started", "message": "백그라운드에서 분석을 실행합니다."}
    return run_analysis(analysis_date, market, limit)
