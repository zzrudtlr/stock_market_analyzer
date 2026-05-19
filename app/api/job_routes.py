from fastapi import APIRouter, BackgroundTasks, Query
from typing import Optional

from app.services.scheduler_service import (
    get_scheduler_status,
    job_advanced_market_ai,
    job_ai_disclosure_analysis,
    job_ai_market_report,
    job_ai_stock_analysis,
    job_auto_watchlist,
    job_chart_pattern_batch,
    job_collect_prices,
    job_collect_stocks,
    job_fundamental_batch,
    job_generate_report,
    job_news_sentiment_batch,
    job_risk_batch,
    job_run_analysis,
    job_supply_demand_batch,
    job_theme_analysis,
    run_advanced_pipeline,
    run_ai_pipeline,
    run_daily_pipeline,
)

router = APIRouter()


@router.get("/status")
def scheduler_status():
    """스케줄러 상태 및 등록된 잡 목록을 반환합니다."""
    return get_scheduler_status()


@router.post("/collect")
def manual_collect(
    background_tasks: BackgroundTasks,
    background: bool = Query(True),
):
    """종목 리스트 + 가격 데이터를 수집합니다."""
    def _run():
        job_collect_stocks()
        job_collect_prices(days=5)

    if background:
        background_tasks.add_task(_run)
        return {"status": "started", "message": "종목 + 가격 수집을 백그라운드로 시작합니다."}
    return _run() or {"status": "done"}


@router.post("/collect/stocks")
def manual_collect_stocks(background_tasks: BackgroundTasks, background: bool = Query(False)):
    """종목 리스트만 수집합니다."""
    if background:
        background_tasks.add_task(job_collect_stocks)
        return {"status": "started", "message": "종목 리스트 수집을 백그라운드로 시작합니다."}
    return job_collect_stocks()


@router.post("/collect/prices")
def manual_collect_prices(
    background_tasks: BackgroundTasks,
    days: int = Query(5, ge=1, le=250),
    background: bool = Query(True),
):
    """가격 데이터를 수집합니다."""
    if background:
        background_tasks.add_task(job_collect_prices, days)
        return {"status": "started", "message": f"최근 {days}일 가격 수집을 백그라운드로 시작합니다."}
    return job_collect_prices(days)


@router.post("/analyze")
def manual_analyze(background_tasks: BackgroundTasks, background: bool = Query(False)):
    """분석을 실행합니다."""
    if background:
        background_tasks.add_task(job_run_analysis)
        return {"status": "started", "message": "분석을 백그라운드로 시작합니다."}
    return job_run_analysis()


@router.post("/report")
def manual_report(background_tasks: BackgroundTasks, background: bool = Query(False)):
    """리포트를 생성합니다."""
    if background:
        background_tasks.add_task(job_generate_report)
        return {"status": "started", "message": "리포트 생성을 백그라운드로 시작합니다."}
    return job_generate_report()


@router.post("/watchlist")
def manual_auto_watchlist(
    background_tasks: BackgroundTasks,
    background: bool = Query(False),
):
    """관심종목 자동 선정을 실행합니다 (분석 결과 기준 단기/장기 upsert)."""
    if background:
        background_tasks.add_task(job_auto_watchlist)
        return {"status": "started", "message": "관심종목 자동 선정을 백그라운드로 시작합니다."}
    return job_auto_watchlist()


@router.post("/run-daily")
def manual_run_daily(background_tasks: BackgroundTasks, background: bool = Query(True)):
    """일일 파이프라인 전체를 수동으로 실행합니다 (수집→분석→AI→리포트)."""
    if background:
        background_tasks.add_task(run_daily_pipeline)
        return {"status": "started", "message": "일일 파이프라인을 백그라운드로 시작합니다."}
    return run_daily_pipeline()


@router.post("/run-ai-analysis")
def manual_run_ai_analysis(
    background_tasks: BackgroundTasks,
    background: bool = Query(True),
):
    """AI 분석 파이프라인(종목AI→공시AI→시장AI리포트)을 실행합니다."""
    if background:
        background_tasks.add_task(run_ai_pipeline)
        return {"status": "started", "message": "AI 분석 파이프라인을 백그라운드로 시작합니다."}
    return run_ai_pipeline()


@router.post("/run-ai-report")
def manual_run_ai_report(
    background_tasks: BackgroundTasks,
    background: bool = Query(False),
):
    """AI 시장 리포트만 생성합니다."""
    if background:
        background_tasks.add_task(job_ai_market_report)
        return {"status": "started", "message": "AI 시장 리포트 생성을 백그라운드로 시작합니다."}
    return job_ai_market_report()


@router.post("/ai-stock")
def manual_ai_stock(
    background_tasks: BackgroundTasks,
    limit: int = Query(30, ge=1, le=100),
    background: bool = Query(True),
):
    """AI 종목 분석 배치를 실행합니다."""
    if background:
        background_tasks.add_task(job_ai_stock_analysis, limit)
        return {"status": "started", "message": f"AI 종목 분석({limit}개)을 백그라운드로 시작합니다."}
    return job_ai_stock_analysis(limit)


@router.post("/ai-disclosure")
def manual_ai_disclosure(background_tasks: BackgroundTasks, background: bool = Query(True)):
    """오늘 공시 종목 AI 분석을 실행합니다."""
    if background:
        background_tasks.add_task(job_ai_disclosure_analysis)
        return {"status": "started", "message": "AI 공시 분석을 백그라운드로 시작합니다."}
    return job_ai_disclosure_analysis()


@router.post("/run-advanced-analysis")
def manual_run_advanced_analysis(
    background_tasks: BackgroundTasks,
    background: bool = Query(True),
):
    """
    고급 전체 파이프라인을 수동으로 실행합니다.

    실행 순서:
    1. 종목 수집 → 2. 가격 수집 → 3. 분석 계산 → 4. 수급 분석 →
    5. 뉴스 분석 → 6. 실적 분석 → 7. 차트 패턴 분석 → 8. 테마 분석 →
    9. 위험도 분석 → 10. AI 종합 시장 분석 → 11. 리포트 저장
    """
    if background:
        background_tasks.add_task(run_advanced_pipeline)
        return {"status": "started", "message": "고급 분석 파이프라인(11단계)을 백그라운드로 시작합니다."}
    return run_advanced_pipeline()


@router.post("/run-beginner-analysis")
def manual_run_beginner_analysis(
    background_tasks: BackgroundTasks,
    background: bool = Query(True),
):
    """
    초보자 친화형 분석 파이프라인을 실행합니다.
    
    실행 순서:
    1. 종목 수집
    2. 가격 수집
    3. 분석 계산
    4. 고급 분석
    5. 초보자 설명 생성
    6. 시장 요약 생성
    7. 리포트 저장
    
    - 기존 DB 구조를 유지하며 초보자용 설명만 생성합니다
    - 모든 분석은 참고용이며 투자 권유가 아닙니다
    """
    if background:
        background_tasks.add_task(run_beginner_pipeline)
        return {
            "status": "started",
            "message": "초보자 친화형 분석 파이프라인(7단계)을 백그라운드로 시작합니다."
        }
    return run_beginner_pipeline()


def run_beginner_pipeline():
    """초보자 분석 파이프라인 실행"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info("초보자 분석 파이프라인 시작")
        
        # 1~4단계: 기존 파이프라인 실행
        logger.info("1단계: 종목 수집")
        job_collect_stocks()
        
        logger.info("2단계: 가격 수집")
        job_collect_prices(days=5)
        
        logger.info("3단계: 분석 계산")
        job_run_analysis()
        
        logger.info("4단계: 고급 분석 (AI, 수급, 뉴스, 실적, 차트 패턴, 테마, 위험도)")
        run_advanced_pipeline()
        
        # 5단계: 초보자 설명 생성 (API를 통해 호출 권장)
        logger.info("5단계: 초보자 설명 생성 (다음 API 호출 필요)")
        logger.info("초보자 설명은 /beginner/stock/{code}/complete-beginner-analysis API를 통해 생성하세요")
        
        # 6단계: 시장 요약 생성
        logger.info("6단계: 시장 요약 생성")
        logger.info("시장 요약은 /beginner/market/simple-summary API를 통해 생성하세요")
        
        # 7단계: 리포트 저장
        logger.info("7단계: 리포트 저장")
        job_generate_report()
        
        logger.info("초보자 분석 파이프라인 완료")
        return {
            "status": "done",
            "message": "초보자 친화형 분석 파이프라인이 완료되었습니다",
            "next_steps": [
                "개별 종목 분석: /beginner/stock/{코드}/complete-beginner-analysis",
                "시장 요약: /beginner/market/simple-summary",
                "용어 설명: /beginner/terms/{용어명}",
                "AI 질문: /beginner/stock/{코드}/ask?question=..."
            ]
        }
    except Exception as e:
        logger.error(f"초보자 분석 파이프라인 실패: {e}")
        return {"status": "error", "message": str(e)}
