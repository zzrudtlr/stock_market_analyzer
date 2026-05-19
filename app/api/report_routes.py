from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.services.report_service import (
    generate_csv_content,
    generate_daily_report,
    get_latest_report,
    get_report_by_date,
    get_reports_list,
)

router = APIRouter()


@router.get("/list")
def list_reports():
    """저장된 리포트 목록을 반환합니다."""
    return get_reports_list()


@router.get("/latest")
def latest_report():
    """가장 최근 리포트(JSON)를 반환합니다."""
    report = get_latest_report()
    if not report:
        return {"message": "리포트가 없습니다. POST /api/reports/generate를 먼저 실행하세요."}
    return report


@router.get("/latest/markdown", response_class=PlainTextResponse)
def latest_report_markdown():
    """가장 최근 리포트를 Markdown으로 반환합니다."""
    report = get_latest_report()
    if not report or not report.get("markdown_content"):
        return "리포트가 없습니다."
    return report["markdown_content"]


@router.get("/latest/html", response_class=HTMLResponse)
def latest_report_html():
    """가장 최근 리포트를 HTML로 반환합니다."""
    report = get_latest_report()
    if not report or not report.get("html_content"):
        return "<p>리포트가 없습니다.</p>"
    return report["html_content"]


@router.get("/latest/csv")
def latest_report_csv():
    """가장 최근 분석 결과를 CSV로 다운로드합니다."""
    report = get_latest_report()
    target_date = date.fromisoformat(report["report_date"]) if report else date.today()
    content = generate_csv_content(target_date)
    return Response(
        content=content.encode("utf-8-sig"),  # BOM 포함 → 엑셀 한글 깨짐 방지
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{target_date}.csv"},
    )


@router.get("/{report_date}")
def get_report(report_date: date):
    """특정 날짜의 리포트(JSON)를 반환합니다."""
    report = get_report_by_date(report_date)
    if not report:
        return {"message": f"{report_date} 리포트가 없습니다. POST /api/reports/generate?report_date={report_date}를 실행하세요."}
    return report


@router.get("/{report_date}/markdown", response_class=PlainTextResponse)
def get_report_markdown(report_date: date):
    """특정 날짜 리포트를 Markdown으로 반환합니다."""
    report = get_report_by_date(report_date)
    if not report or not report.get("markdown_content"):
        return f"{report_date} 리포트가 없습니다."
    return report["markdown_content"]


@router.get("/{report_date}/html", response_class=HTMLResponse)
def get_report_html(report_date: date):
    """특정 날짜 리포트를 HTML로 반환합니다."""
    report = get_report_by_date(report_date)
    if not report or not report.get("html_content"):
        return "<p>리포트가 없습니다.</p>"
    return report["html_content"]


@router.get("/{report_date}/csv")
def get_report_csv(report_date: date):
    """특정 날짜 분석 결과를 CSV로 다운로드합니다."""
    content = generate_csv_content(report_date)
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{report_date}.csv"},
    )


@router.post("/generate")
def generate_report(
    background_tasks: BackgroundTasks,
    report_date: Optional[date] = Query(None, description="리포트 날짜 (기본: 오늘)"),
    background: bool = Query(False, description="백그라운드 실행 여부"),
):
    """일일 리포트를 생성합니다 (Markdown + HTML + JSON + CSV 지원)."""
    if background:
        background_tasks.add_task(generate_daily_report, report_date)
        return {"status": "started", "message": "백그라운드에서 리포트를 생성합니다."}
    return generate_daily_report(report_date)
