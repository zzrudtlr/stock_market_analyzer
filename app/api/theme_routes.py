from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.theme_analysis_service import get_theme_analysis, run_theme_analysis

router = APIRouter()


@router.post("/run")
def theme_analysis_run(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None, description="분석 기준일 (기본: 오늘)"),
    background: bool = Query(True, description="백그라운드 실행 여부"),
):
    """
    테마별 강세/약세 흐름을 분석합니다.
    기존 stock_analysis_results 데이터를 테마로 집계하고 AI 해설을 생성합니다.
    참고용 시장 흐름 분석이며 투자 권유가 아닙니다.
    """
    if background:
        background_tasks.add_task(run_theme_analysis, analysis_date)
        return {
            "status": "started",
            "message": "테마 분석을 백그라운드에서 실행합니다.",
            "date": str(analysis_date or date.today()),
        }
    return run_theme_analysis(analysis_date)


@router.get("/{report_date}")
def theme_analysis_get(report_date: date):
    """지정 날짜의 테마 분석 결과를 반환합니다."""
    rows = get_theme_analysis(report_date)
    if not rows:
        return {"status": "not_found", "date": str(report_date), "themes": []}
    return {"status": "ok", "date": str(report_date), "count": len(rows), "themes": rows}


@router.get("")
def theme_analysis_today(analysis_date: Optional[date] = Query(None)):
    """오늘 또는 지정일의 테마 분석 결과를 반환합니다."""
    target = analysis_date or date.today()
    rows = get_theme_analysis(target)
    if not rows:
        return {
            "status": "not_found",
            "date": str(target),
            "message": "테마 분석 데이터가 없습니다. POST /api/theme/run 을 먼저 실행하세요.",
            "themes": [],
        }
    return {"status": "ok", "date": str(target), "count": len(rows), "themes": rows}
