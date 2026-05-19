"""
종합 시장 AI 해설 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("")
def get_latest_advanced_market_ai(
    report_date: Optional[date] = Query(None, description="조회 기준일 (기본: 최신)"),
):
    """종합 시장 AI 해설 조회 (최신 또는 특정 날짜)."""
    from app.services.advanced_market_ai_service import get_advanced_market_ai
    result = get_advanced_market_ai(report_date)
    if not result:
        return {"status": "not_found", "report_date": str(report_date) if report_date else "latest"}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.post("/generate")
def generate_advanced_market_ai(
    background_tasks: BackgroundTasks,
    report_date: Optional[date] = Query(None, description="분석 기준일 (기본: 오늘)"),
    model: str = Query("gpt-4o-mini", description="사용 AI 모델"),
    force_regenerate: bool = Query(False, description="기존 결과 덮어쓰기"),
    background: bool = Query(False, description="백그라운드 실행"),
):
    """종합 시장 AI 해설 생성."""
    from app.services.advanced_market_ai_service import generate_advanced_market_ai
    target_date = report_date or date.today()
    if background:
        background_tasks.add_task(generate_advanced_market_ai, target_date, model, force_regenerate)
        return {
            "status": "started",
            "message": f"{target_date} 종합 시장 AI 해설 생성을 백그라운드로 시작합니다.",
            "disclaimer": DISCLAIMER,
        }
    result = generate_advanced_market_ai(target_date, model, force_regenerate)
    return {**result, "disclaimer": DISCLAIMER}
