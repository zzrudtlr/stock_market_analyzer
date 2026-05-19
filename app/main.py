"""
Stock Market Analyzer - FastAPI 메인 앱
실행: python app/main.py  또는  uvicorn app.main:app --reload
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (python app/main.py 직접 실행 지원)
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import ai_routes, analysis_routes, job_routes, report_routes, stock_routes, watchlist_routes, theme_routes, themes_routes, supply_demand_routes, news_sentiment_routes, fundamental_routes, chart_pattern_routes, market_leader_routes, theme_rotation_routes, risk_routes, advanced_market_ai_routes, market_date_analysis_routes
from app.api import beginner_friendly_routes
from app.config import DISCLAIMER
from app.database import test_connection
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Stock Market Analyzer 시작")
    if test_connection():
        logger.info("MySQL 연결 성공")
        # stock_ai_analysis 테이블 없으면 자동 생성 (기존 테이블 영향 없음)
        try:
            from app.database import get_engine
            from app.models.ai_analysis import StockAIAnalysis
            from app.models.disclosure_ai_analysis import DisclosureAIAnalysis
            from app.models.market_report_ai import MarketReportAI
            from app.models.theme_analysis import ThemeAnalysis
            from app.models.theme_analysis_result import ThemeAnalysisResult
            from app.models.supply_demand_analysis import SupplyDemandAnalysis
            from app.models.news_sentiment_result import NewsSentimentResult
            from app.models.fundamental_analysis_result import FundamentalAnalysisResult
            from app.models.chart_pattern_analysis_result import ChartPatternAnalysisResult
            from app.models.market_leader_result import MarketLeaderResult, MarketLeaderSummary
            from app.models.theme_rotation_result import ThemeRotationResult, ThemeRotationSummary
            from app.models.risk_analysis_result import RiskAnalysisResult
            from app.models.advanced_market_ai import AdvancedMarketAI
            engine = get_engine()
            StockAIAnalysis.__table__.create(bind=engine, checkfirst=True)
            DisclosureAIAnalysis.__table__.create(bind=engine, checkfirst=True)
            MarketReportAI.__table__.create(bind=engine, checkfirst=True)
            ThemeAnalysis.__table__.create(bind=engine, checkfirst=True)
            ThemeAnalysisResult.__table__.create(bind=engine, checkfirst=True)
            SupplyDemandAnalysis.__table__.create(bind=engine, checkfirst=True)
            NewsSentimentResult.__table__.create(bind=engine, checkfirst=True)
            FundamentalAnalysisResult.__table__.create(bind=engine, checkfirst=True)
            ChartPatternAnalysisResult.__table__.create(bind=engine, checkfirst=True)
            MarketLeaderResult.__table__.create(bind=engine, checkfirst=True)
            MarketLeaderSummary.__table__.create(bind=engine, checkfirst=True)
            ThemeRotationResult.__table__.create(bind=engine, checkfirst=True)
            ThemeRotationSummary.__table__.create(bind=engine, checkfirst=True)
            RiskAnalysisResult.__table__.create(bind=engine, checkfirst=True)
            AdvancedMarketAI.__table__.create(bind=engine, checkfirst=True)
            logger.info("AI 분석 테이블 확인 완료")
        except Exception as e:
            logger.warning(f"AI 테이블 생성 스킵: {e}")
    else:
        logger.error("MySQL 연결 실패 - .env 파일을 확인하세요")
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"스케줄러 시작 실패 (서버는 계속 실행): {e}")
    yield
    stop_scheduler()
    logger.info("Stock Market Analyzer 종료")


app = FastAPI(
    title="Stock Market Analyzer",
    description="한국 주식 시장 데이터 분석 도구 (참고용 - 투자 권유 아님)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def inject_disclaimer(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "application/json" not in ct:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        data = json.loads(body)
        if isinstance(data, dict) and "disclaimer" not in data:
            data["disclaimer"] = DISCLAIMER
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    except Exception:
        pass
    return Response(
        content=body,
        status_code=response.status_code,
        media_type="application/json",
        headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
    )

app.include_router(stock_routes.router, prefix="/api/stocks", tags=["종목"])
app.include_router(analysis_routes.router, prefix="/api/analysis", tags=["분석"])
app.include_router(report_routes.router, prefix="/api/reports", tags=["리포트"])
app.include_router(job_routes.router, prefix="/jobs", tags=["스케줄러"])
app.include_router(watchlist_routes.router, prefix="/api/watchlist", tags=["관심종목"])
app.include_router(ai_routes.router,       prefix="/ai",             tags=["AI 분석"])
app.include_router(theme_routes.router,    prefix="/api/theme",      tags=["테마 분석"])
app.include_router(themes_routes.router,        prefix="/api/themes",        tags=["테마 분석 v2"])
app.include_router(supply_demand_routes.router, prefix="/api/supply-demand", tags=["수급 분석"])
app.include_router(news_sentiment_routes.router, prefix="/api/news", tags=["뉴스 감성"])
app.include_router(fundamental_routes.router,      prefix="/api/fundamental",    tags=["펀더멘털"])
app.include_router(chart_pattern_routes.router,   prefix="/api/chart-pattern",  tags=["차트 패턴"])
app.include_router(market_leader_routes.router,    prefix="/api/market-leader",   tags=["시장 주도주"])
app.include_router(theme_rotation_routes.router,  prefix="/api/theme-rotation",  tags=["테마 순환"])
app.include_router(risk_routes.router,            prefix="/api/risk",            tags=["위험도 분석"])
app.include_router(advanced_market_ai_routes.router, prefix="/api/advanced-market-ai", tags=["종합 시장 AI"])
app.include_router(market_date_analysis_routes.router, prefix="/api/analysis", tags=["특정 날짜 분석"])
app.include_router(beginner_friendly_routes.router, tags=["초보자 분석"])


@app.get("/")
def root():
    return {
        "service": "Stock Market Analyzer",
        "disclaimer": DISCLAIMER,
        "docs": "/docs",
        "endpoints": {
            "종목 수집": "POST /api/collect/stocks",
            "시세 수집(오늘)": "POST /api/collect/prices",
            "시세 수집(N일)": "POST /api/collect/prices/bulk?days=60",
            "시장지수 수집": "POST /api/collect/indices",
            "분석 실행": "POST /api/analysis/run",
            "특정 날짜 시장 분석": "POST /api/analysis/market-date-analysis?analysis_date=2026-05-20&top_count=5",
            "리포트 생성": "POST /api/reports/generate",
            "강세 TOP20": "GET /api/analysis/bullish",
            "약세 TOP20": "GET /api/analysis/bearish",
            "종목 목록": "GET /api/stocks",
            "최신 리포트": "GET /api/reports/latest",
            "관심종목 자동 선정": "POST /api/watchlist/auto-select",
            "AI 종목 분석":      "POST /ai/analyze/{stock_code}",
            "AI 일괄 분석":      "POST /ai/analyze/daily/batch",
            "AI 해설 조회":      "GET /ai/summary/{stock_code}",
            "AI 공시 분석":      "POST /ai/disclosures/analyze?stock_code={code}",
            "AI 공시 조회":      "GET /ai/disclosures/{stock_code}",
            "AI 시장 리포트 생성": "POST /ai/report/generate",
            "AI 시장 리포트 조회": "GET /ai/report/{date}",
            "테마 분석 실행":     "POST /api/theme/run",
            "테마 분석 조회":     "GET /api/theme",
            "테마 분석 v2 전체":  "GET /api/themes",
            "테마 강세 목록":     "GET /api/themes/strong",
            "테마 약세 목록":     "GET /api/themes/weak",
            "테마 상세":          "GET /api/themes/{theme_name}",
            "테마 분석 v2 실행":  "POST /api/themes/analyze/daily",
            "스케줄러 상태": "GET /jobs/status",
            "일일 파이프라인 수동 실행": "POST /jobs/run-daily",
            "수집만 실행": "POST /jobs/collect",
            "분석만 실행": "POST /jobs/analyze",
            "리포트만 실행": "POST /jobs/report",
            "특정 날짜 분석(경로)": "GET /api/analysis/market-date-analysis/2026-05-20",
        },
    }


@app.get("/health")
def health():
    ok = test_connection()
    return {"db": "ok" if ok else "error", "status": "ok" if ok else "degraded"}


@app.get("/db-check")
def db_check():
    """DB 연결 상태 및 접속 정보를 상세히 반환합니다."""
    from app.config import settings
    from sqlalchemy import text
    try:
        from app.database import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        return {
            "status": "connected",
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
            "database": db_name,
            "mysql_version": version,
        }
    except Exception as e:
        logger.error(f"DB check 실패: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(e)},
        )


# === 데이터 수집 엔드포인트 ===

@app.post("/api/collect/stocks", tags=["수집"])
def collect_stocks():
    """KOSPI + KOSDAQ 종목 리스트를 수집합니다."""
    from app.collectors.finance_data_reader_collector import collect_stock_list
    return collect_stock_list()


@app.post("/api/collect/prices", tags=["수집"])
def collect_prices_today():
    """오늘 날짜의 전체 시세를 수집합니다 (FDR 사용, pykrx 대체)."""
    from app.collectors.finance_data_reader_collector import collect_prices_bulk_fdr
    return collect_prices_bulk_fdr(days=1)


@app.post("/api/collect/prices/bulk", tags=["수집"])
def collect_prices_bulk(
    background_tasks: BackgroundTasks,
    days: int = Query(60, ge=1, le=250),
    background: bool = Query(True),
):
    """최근 N일치 시세를 FDR로 일괄 수집합니다. (pykrx → FDR로 교체됨)"""
    from app.collectors.finance_data_reader_collector import collect_prices_bulk_fdr
    if background:
        background_tasks.add_task(collect_prices_bulk_fdr, days)
        return {"status": "started", "message": f"최근 {days}일 시세 FDR 수집을 백그라운드로 시작합니다."}
    return collect_prices_bulk_fdr(days)


@app.post("/api/collect/prices/fdr/{stock_code}", tags=["수집"])
def collect_prices_fdr(stock_code: str, days: int = Query(60, ge=5, le=250)):
    """단일 종목 시세를 FDR로 수집합니다 (pykrx 대체용)."""
    from app.collectors.finance_data_reader_collector import collect_stock_prices_fdr
    return collect_stock_prices_fdr(stock_code, days)


@app.post("/api/collect/prices/bulk/fdr", tags=["수집"])
def collect_prices_bulk_fdr_endpoint(
    background_tasks: BackgroundTasks,
    days: int = Query(60, ge=5, le=250),
    limit: Optional[int] = Query(None, description="테스트용 종목 수 제한"),
    background: bool = Query(True),
):
    """전체 종목 시세를 FDR로 일괄 수집합니다 (pykrx 인증 불필요)."""
    from app.collectors.finance_data_reader_collector import collect_prices_bulk_fdr
    if background:
        background_tasks.add_task(collect_prices_bulk_fdr, days, limit)
        return {"status": "started", "message": f"FDR로 {days}일 시세 수집을 백그라운드로 시작합니다."}
    return collect_prices_bulk_fdr(days, limit)


@app.post("/api/collect/indices", tags=["수집"])
def collect_indices(days: int = Query(60, ge=5, le=250)):
    """시장 지수(KOSPI, KOSDAQ) 데이터를 수집합니다."""
    from app.collectors.finance_data_reader_collector import collect_market_indices
    return collect_market_indices(days)


@app.post("/api/collect/all", tags=["수집"])
def collect_all(background_tasks: BackgroundTasks, days: int = Query(60)):
    """종목 리스트 + 지수 + N일 시세를 순서대로 수집합니다 (백그라운드). pykrx 대신 FDR 사용."""
    from app.collectors.finance_data_reader_collector import (
        collect_market_indices,
        collect_stock_list,
        collect_prices_bulk_fdr,
    )

    def _run():
        logger.info("=== 전체 수집 시작 (FDR) ===")
        collect_stock_list()
        collect_market_indices(days)
        collect_prices_bulk_fdr(days)
        logger.info("=== 전체 수집 완료 ===")

    background_tasks.add_task(_run)
    return {"status": "started", "message": f"종목+지수+시세({days}일) FDR 수집을 백그라운드로 시작합니다."}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
