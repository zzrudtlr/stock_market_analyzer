"""
시장 주도주 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("/summary")
def get_market_leader_summary(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
):
    """당일 시장 주도주 요약 (AI 해설 + 상위 리스트 포함)."""
    from app.services.market_leader_analysis_service import get_market_summary
    result = get_market_summary(analysis_date)
    if not result:
        return {"status": "not_found", "message": "분석 데이터 없음 — 먼저 /batch 를 실행하세요."}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.get("")
def get_market_leaders(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    signal: Optional[str] = Query(None, description="시그널 필터 (시장 주도주/주도 후보/관심 종목/일반)"),
    market: Optional[str] = Query(None, description="시장 필터 (KOSPI/KOSDAQ)"),
    limit: int = Query(50, ge=1, le=200),
):
    """시장 주도 점수 상위 종목 목록."""
    from app.services.market_leader_analysis_service import get_market_leaders
    items = get_market_leaders(analysis_date, limit=limit, signal=signal, market=market)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.get("/trading-value")
def get_trading_value_leaders(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    market: Optional[str] = Query(None, description="시장 필터 (KOSPI/KOSDAQ)"),
    limit: int = Query(30, ge=1, le=100),
):
    """거래대금 상위 종목 목록."""
    from app.services.market_leader_analysis_service import get_market_leaders_by_trading_value
    items = get_market_leaders_by_trading_value(analysis_date, limit=limit, market=market)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.post("/batch")
def batch_market_leader_analysis(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(500, ge=100, le=2000),
    with_ai: bool = Query(True),
    background: bool = Query(True),
):
    """전체 시장 주도주 분석 실행 (거래대금 상위 N종목 대상)."""
    from app.services.market_leader_analysis_service import run_market_leader_analysis
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_market_leader_analysis, target_date, limit, with_ai)
        return {
            "status": "started",
            "message": f"{target_date} 시장 주도주 분석 시작 (최대 {limit}종목)",
            "disclaimer": DISCLAIMER,
        }
    result = run_market_leader_analysis(target_date, limit, with_ai)
    return {**result, "disclaimer": DISCLAIMER}
