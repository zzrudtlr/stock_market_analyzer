"""
테마 분석 API — 확장 엔드포인트 (/api/themes)

기존 /api/theme 라우터와 별개로 새 분석 결과(theme_analysis_results)를 제공합니다.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.theme_analysis_service import (
    get_theme_analysis,
    get_theme_detail,
    get_themes_by_signal,
    run_theme_analysis,
)

router = APIRouter()

_STRONG_SIGNALS = {"매우 강세", "강세 흐름"}
_WEAK_SIGNALS   = {"약세 흐름", "하락 주의"}


@router.get("")
def themes_today(analysis_date: Optional[date] = Query(None)):
    """오늘(또는 지정일) 전체 테마 분석 결과."""
    target = analysis_date or date.today()
    themes = get_theme_analysis(target)
    if not themes:
        return {
            "status": "not_found",
            "date": str(target),
            "message": "테마 분석 데이터가 없습니다. POST /api/themes/analyze/daily 를 먼저 실행하세요.",
            "themes": [],
        }
    return {"status": "ok", "date": str(target), "count": len(themes), "themes": themes}


@router.get("/strong")
def themes_strong(analysis_date: Optional[date] = Query(None)):
    """강세 테마 목록 (매우 강세 + 강세 흐름)."""
    target = analysis_date or date.today()
    themes = get_theme_analysis(target)
    strong = [t for t in themes if t["theme_signal"] in _STRONG_SIGNALS]
    return {"status": "ok", "date": str(target), "count": len(strong), "themes": strong}


@router.get("/weak")
def themes_weak(analysis_date: Optional[date] = Query(None)):
    """약세 테마 목록 (약세 흐름 + 하락 주의)."""
    target = analysis_date or date.today()
    themes = get_theme_analysis(target)
    weak = [t for t in themes if t["theme_signal"] in _WEAK_SIGNALS]
    return {"status": "ok", "date": str(target), "count": len(weak), "themes": weak}


@router.get("/rotation")
def themes_rotation(analysis_date: Optional[date] = Query(None)):
    """순환매 관심 테마 목록."""
    target = analysis_date or date.today()
    return {
        "status": "ok",
        "date": str(target),
        "themes": get_themes_by_signal("순환매 관심", target),
    }


@router.post("/analyze/daily")
def themes_analyze_daily(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    background: bool = Query(True),
):
    """
    테마별 강세/약세 분석을 실행합니다.
    참고용 시장 흐름 분석이며 투자 권유가 아닙니다.
    """
    target = analysis_date or date.today()
    if background:
        background_tasks.add_task(run_theme_analysis, target)
        return {
            "status": "started",
            "message": "테마 분석을 백그라운드에서 실행합니다.",
            "date": str(target),
        }
    return run_theme_analysis(target)


@router.get("/{theme_name}")
def theme_detail(theme_name: str, analysis_date: Optional[date] = Query(None)):
    """특정 테마의 상세 분석 결과."""
    target = analysis_date or date.today()
    detail = get_theme_detail(theme_name, target)
    if not detail:
        return {
            "status": "not_found",
            "date": str(target),
            "theme_name": theme_name,
            "message": f"'{theme_name}' 테마 데이터를 찾을 수 없습니다.",
        }
    return {"status": "ok", "date": str(target), **detail}
