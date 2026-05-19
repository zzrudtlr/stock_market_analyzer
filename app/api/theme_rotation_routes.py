"""
테마 순환 분석 API 라우터
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

router = APIRouter()

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."


@router.get("/summary")
def get_theme_rotation_summary(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
):
    """당일 순환매 요약 (오전/오후/마감 강세 테마 + AI 해설)."""
    from app.services.theme_rotation_analysis_service import get_theme_rotation_summary
    result = get_theme_rotation_summary(analysis_date)
    if not result:
        return {"status": "not_found", "message": "분석 데이터 없음 — 먼저 /analyze 를 실행하세요."}
    return {"status": "success", "data": result, "disclaimer": DISCLAIMER}


@router.get("")
def get_theme_rotation_results(
    analysis_date: Optional[date] = Query(None, description="기준일 (기본: 최신)"),
    signal: Optional[str] = Query(
        None,
        description="시그널 필터 (순환매 유입/유지 강세/횡보/이탈/약세 지속)",
    ),
    limit: int = Query(50, ge=1, le=100),
):
    """테마별 순환 분석 결과 목록 (intraday 순위 오름차순)."""
    from app.services.theme_rotation_analysis_service import get_theme_rotation_results
    items = get_theme_rotation_results(analysis_date, signal=signal, limit=limit)
    return {"status": "success", "count": len(items), "items": items, "disclaimer": DISCLAIMER}


@router.post("/analyze")
def analyze_theme_rotation(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    with_ai: bool = Query(True),
    background: bool = Query(True),
):
    """테마 순환 분석 실행."""
    from app.services.theme_rotation_analysis_service import run_theme_rotation_analysis
    target_date = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_theme_rotation_analysis, target_date, with_ai)
        return {
            "status": "started",
            "message": f"{target_date} 테마 순환 분석 시작",
            "disclaimer": DISCLAIMER,
        }
    result = run_theme_rotation_analysis(target_date, with_ai)
    return {**result, "disclaimer": DISCLAIMER}
