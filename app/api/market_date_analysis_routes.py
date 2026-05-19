"""
특정 날짜 시장 분석 API 엔드포인트

커스텀 명령어 시스템: /market-analysis 2026-05-20
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query, Path

from app.services.market_date_analysis_service import MarketDateAnalysisService

router = APIRouter()


@router.post("/market-date-analysis")
def analyze_market_by_date(
    analysis_date: date = Query(..., description="분석 대상 날짜 (YYYY-MM-DD)"),
    top_count: int = Query(5, ge=1, le=20, description="상위 N개 종목"),
    include_mixed: bool = Query(True, description="혼합 신호 종목 포함 여부"),
    save_report: bool = Query(True, description="분석 리포트 저장 여부"),
):
    """
    특정 날짜의 시장을 분석하고 강세/약세 종목을 정리합니다.

    **분석 내용:**
    - 강세 예상 종목 TOP N (긍정 신호 강한 순)
    - 약세 예상 종목 TOP N (위험 신호 강한 순)
    - 주의 종목 (혼합 신호)
    - 시장 종합 의견

    **각 종목 분석:**
    - 3~5개 근거 제시
    - 초보자도 이해하기 쉬운 설명
    - 위험 요소 포함

    **출력:**
    ```json
    {
        "status": "success",
        "analysis_date": "2026-05-20",
        "bullish_stocks": [...],      // 강세 예상 종목
        "bearish_stocks": [...],      // 약세 주의 종목
        "mixed_signal_stocks": [...], // 혼합 신호 종목
        "market_overview": {...},     // 시장 종합 의견
        "analysis_summary": "...",    // 분석 요약
        "disclaimer": "..."           // 면책 사항
    }
    ```

    **예시:**
    ```
    POST /analysis/market-date-analysis?analysis_date=2026-05-20&top_count=5
    ```
    """
    # 분석 실행
    result = MarketDateAnalysisService.analyze_market_by_date(
        analysis_date=analysis_date,
        top_count=top_count,
        include_mixed_signals=include_mixed,
    )

    # 리포트 저장
    if save_report and result.get("status") == "success":
        try:
            filepath = MarketDateAnalysisService.save_analysis_report(result)
            result["report_saved"] = filepath
        except Exception as e:
            result["report_save_error"] = str(e)

    return result


@router.get("/market-date-analysis/{date_str}")
def get_market_analysis_by_date_str(
    date_str: str,
    top_count: int = Query(5, ge=1, le=20),
    include_mixed: bool = Query(True),
):
    """
    URL 경로에 날짜를 입력하여 시장 분석을 조회합니다.

    **사용 예시:**
    ```
    GET /analysis/market-date-analysis/2026-05-20?top_count=5
    ```
    """
    try:
        analysis_date = date.fromisoformat(date_str)
        return MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=analysis_date,
            top_count=top_count,
            include_mixed_signals=include_mixed,
        )
    except ValueError:
        return {
            "status": "error",
            "message": f"날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식을 사용하세요. (입력: {date_str})",
        }


@router.get("/market-date-analysis/recent/{days}")
def get_recent_market_analyses(days: int = Path(..., ge=1, le=30)):
    """
    최근 N일 동안의 시장 분석 결과를 조회합니다.
    (구현 예정: 향후 히스토리 조회 기능)

    **사용 예시:**
    ```
    GET /analysis/market-date-analysis/recent/5
    ```
    """
    return {
        "status": "not_implemented",
        "message": f"최근 {days}일 분석 조회는 향후 구현 예정입니다.",
    }
