from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.ai_analysis_service import analyze_daily_batch, analyze_stock, get_ai_analysis
from app.services.disclosure_ai_service import (
    analyze_disclosure_by_id,
    analyze_stock_disclosures,
    get_disclosure_analysis,
)
from app.services.market_report_ai_service import generate_market_report, get_market_report

router = APIRouter()


@router.post("/analyze/{stock_code}")
def ai_analyze_stock(
    stock_code: str,
    analysis_date: Optional[date] = Query(None, description="분석 기준 날짜 (기본: 오늘)"),
):
    """특정 종목에 대한 AI 분석 해설을 생성합니다 (참고용)."""
    return analyze_stock(stock_code, analysis_date)


@router.post("/analyze/daily/batch")
def ai_analyze_daily(
    background_tasks: BackgroundTasks,
    analysis_date: Optional[date] = Query(None),
    limit: int = Query(30, ge=1, le=200, description="처리할 최대 종목 수"),
    skip_existing: bool = Query(True, description="이미 분석된 종목 건너뜀"),
    background: bool = Query(True),
):
    """오늘 분석 상위 종목에 대해 AI 해설을 일괄 생성합니다 (참고용)."""
    if background:
        background_tasks.add_task(analyze_daily_batch, analysis_date, limit, skip_existing)
        return {"status": "started", "message": f"AI 일괄 분석 ({limit}개)을 백그라운드로 시작합니다."}
    return analyze_daily_batch(analysis_date, limit, skip_existing)


@router.get("/summary/{stock_code}")
def ai_get_summary(
    stock_code: str,
    analysis_date: Optional[date] = Query(None),
):
    """종목의 최근 AI 분석 해설을 조회합니다."""
    result = get_ai_analysis(stock_code, analysis_date)
    if not result:
        return {
            "status": "not_found",
            "message": f"{stock_code} AI 분석 결과가 없습니다. POST /ai/analyze/{stock_code} 로 생성하세요.",
        }
    return {"status": "ok", **result}


# ── 공시 AI 분석 ──────────────────────────────────────────────

@router.post("/disclosures/analyze")
def ai_analyze_disclosures(
    stock_code: str = Query(..., description="종목코드"),
    limit: int = Query(5, ge=1, le=20, description="분석할 최근 공시 수"),
    skip_existing: bool = Query(True, description="이미 분석된 공시 건너뜀"),
):
    """종목의 최근 공시에 대해 AI 분석을 실행합니다 (참고용)."""
    return analyze_stock_disclosures(stock_code, limit=limit, skip_existing=skip_existing)


@router.post("/disclosures/analyze/{disclosure_id}")
def ai_analyze_single_disclosure(disclosure_id: int):
    """단일 공시 ID에 대해 AI 분석을 실행합니다 (참고용)."""
    return analyze_disclosure_by_id(disclosure_id)


@router.get("/disclosures/{stock_code}")
def ai_get_disclosures(
    stock_code: str,
    limit: int = Query(10, ge=1, le=50, description="조회할 최대 건수"),
):
    """종목의 저장된 공시 AI 분석 결과를 조회합니다."""
    results = get_disclosure_analysis(stock_code, limit=limit)
    if not results:
        return {
            "status": "not_found",
            "message": f"{stock_code} 공시 AI 분석 결과가 없습니다. POST /ai/disclosures/analyze 로 생성하세요.",
        }
    return {"status": "ok", "stock_code": stock_code, "count": len(results), "items": results}


# ── AI 시장 리포트 ────────────────────────────────────────────

@router.post("/report/generate")
def ai_generate_market_report(
    report_date: Optional[date] = Query(None, description="리포트 기준 날짜 (기본: 오늘)"),
    background: bool = Query(False),
    background_tasks: BackgroundTasks = None,
):
    """시장 데이터를 기반으로 AI 시장 리포트를 생성합니다 (참고용)."""
    if background and background_tasks:
        background_tasks.add_task(generate_market_report, report_date)
        return {"status": "started", "message": "AI 시장 리포트 생성을 백그라운드로 시작합니다."}
    return generate_market_report(report_date)


@router.get("/report/{report_date}")
def ai_get_market_report(report_date: date):
    """저장된 AI 시장 리포트를 조회합니다."""
    result = get_market_report(report_date)
    if not result:
        return {
            "status": "not_found",
            "message": f"{report_date} AI 시장 리포트가 없습니다. POST /ai/report/generate 로 생성하세요.",
        }
    return {"status": "ok", **result}
