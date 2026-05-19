from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.services.watchlist_service import auto_select_watchlist

router = APIRouter()


@router.post("/auto-select")
def auto_select(
    analysis_date: Optional[date] = Query(None, description="분석 기준 날짜 (기본: 오늘)"),
):
    """분석 결과 기준으로 단기/장기 관심종목을 자동 선정하여 watchlist에 upsert합니다."""
    return auto_select_watchlist(analysis_date)
