"""
스케줄러 서비스 - APScheduler 기반 일일 자동 실행

파이프라인 A (REPORT_TIME, 기본 18:30 KST):
  1. 종목 리스트 수집
  2. 일별 가격 데이터 수집 (FDR)
  3. 분석 실행
  4. 관심종목 자동 선정
  5. AI 종목 분석
  6. AI 공시 분석
  7. AI 시장 리포트 생성
  8. 리포트 저장

파이프라인 B (AI_REPORT_TIME, 기본 19:00 KST):
  AI 분석 파이프라인 단독 실행 (5~7 단계만)
"""
import logging
from datetime import date, datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import get_db_session
from app.models.collector_log import CollectorLog

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


# ── 로그 헬퍼 ────────────────────────────────────────────────────

def _save_log(name: str, status: str, message: str, started_at: datetime) -> None:
    session = get_db_session()
    try:
        log = CollectorLog(
            collector_name=name,
            target_date=date.today(),
            status=status,
            message=message[:2000] if message else None,
            started_at=started_at,
            finished_at=datetime.now(),
        )
        session.add(log)
        session.commit()
    except Exception as e:
        logger.error(f"[스케줄러] 로그 저장 실패: {e}")
        session.rollback()
    finally:
        session.close()


# ── 개별 작업 ────────────────────────────────────────────────────

def job_collect_stocks() -> dict:
    """종목 리스트 수집 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] 종목 리스트 수집 시작")
    try:
        from app.collectors.finance_data_reader_collector import collect_stock_list
        result = collect_stock_list()
        status = result.get("status", "unknown")
        msg = f"종목 수집 완료: {result.get('count', 0)}건"
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_collect_stocks", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 종목 수집 실패: {e}", exc_info=True)
        _save_log("scheduler_collect_stocks", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_collect_prices(days: int = 1) -> dict:
    """일별 가격 수집 작업 (FDR 방식)"""
    started_at = datetime.now()
    logger.info(f"[스케줄러] 가격 데이터 수집 시작 ({days}일)")
    try:
        if days <= 1:
            from app.collectors.finance_data_reader_collector import collect_prices_bulk_fdr
            result = collect_prices_bulk_fdr(days=5)   # 최소 5일치 보정
        else:
            from app.collectors.finance_data_reader_collector import collect_prices_bulk_fdr
            result = collect_prices_bulk_fdr(days=days)
        status = result.get("status", "unknown")
        msg = (
            f"가격 수집 완료: 성공={result.get('success', 0)}, "
            f"에러={result.get('errors', 0)}, 전체={result.get('total', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_collect_prices", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 가격 수집 실패: {e}", exc_info=True)
        _save_log("scheduler_collect_prices", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_run_analysis() -> dict:
    """분석 실행 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] 분석 실행 시작")
    try:
        from app.services.analysis_service import run_analysis
        result = run_analysis()
        status = result.get("status", "unknown")
        msg = (
            f"분석 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 에러={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_analysis", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 분석 실패: {e}", exc_info=True)
        _save_log("scheduler_analysis", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_auto_watchlist() -> dict:
    """관심종목 자동 선정 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] 관심종목 자동 선정 시작")
    try:
        from app.services.watchlist_service import auto_select_watchlist
        result = auto_select_watchlist()
        status = result.get("status", "unknown")
        s = result.get("short_term", {})
        l = result.get("long_term", {})
        msg = (
            f"자동선정 완료: 단기={s.get('selected', 0)}개"
            f"(신규{s.get('inserted', 0)}/업데이트{s.get('updated', 0)}), "
            f"장기={l.get('selected', 0)}개"
            f"(신규{l.get('inserted', 0)}/업데이트{l.get('updated', 0)})"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_auto_watchlist", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 관심종목 자동 선정 실패: {e}", exc_info=True)
        _save_log("scheduler_auto_watchlist", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_generate_report() -> dict:
    """리포트 생성 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] 리포트 생성 시작")
    try:
        from app.services.report_service import generate_daily_report
        result = generate_daily_report()
        status = result.get("status", "unknown")
        msg = f"리포트 생성 완료: {result.get('date', '-')}"
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_report", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 리포트 생성 실패: {e}", exc_info=True)
        _save_log("scheduler_report", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_ai_stock_analysis(limit: int = 30) -> dict:
    """AI 종목 분석 작업 — analyze_daily_batch 호출"""
    started_at = datetime.now()
    logger.info(f"[스케줄러] AI 종목 분석 시작 (최대 {limit}종목)")
    try:
        from app.services.ai_analysis_service import analyze_daily_batch
        result = analyze_daily_batch(limit=limit, skip_existing=True)
        status = result.get("status", "unknown")
        msg = (
            f"AI 종목 분석 완료: 처리={result.get('processed', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_ai_stock", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] AI 종목 분석 실패: {e}", exc_info=True)
        _save_log("scheduler_ai_stock", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_ai_disclosure_analysis() -> dict:
    """AI 공시 분석 작업 — 오늘 공시 종목 전체 분석"""
    started_at = datetime.now()
    logger.info("[스케줄러] AI 공시 분석 시작")
    try:
        from sqlalchemy import select
        from app.models.disclosure import Disclosure
        from app.services.disclosure_ai_service import analyze_stock_disclosures

        today = date.today()
        session = get_db_session()
        try:
            codes = session.execute(
                select(Disclosure.stock_code)
                .where(
                    Disclosure.report_date == today,
                    Disclosure.stock_code.isnot(None),
                )
                .distinct()
            ).scalars().all()
        finally:
            session.close()

        if not codes:
            msg = f"오늘({today}) 공시 종목 없음 — 스킵"
            logger.info(f"[스케줄러] {msg}")
            _save_log("scheduler_ai_disclosure", "success", msg, started_at)
            return {"status": "success", "message": msg, "stocks": 0, "processed": 0}

        total_processed = total_errors = 0
        for code in codes:
            r = analyze_stock_disclosures(code, limit=5, skip_existing=True)
            if r.get("status") in ("success", "partial"):
                total_processed += r.get("processed", 0)
            else:
                total_errors += 1

        status = "success" if total_errors == 0 else "partial"
        msg = (
            f"AI 공시 분석 완료: 종목={len(codes)}개, "
            f"처리={total_processed}건, 오류종목={total_errors}개"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_ai_disclosure", status, msg, started_at)
        return {"status": status, "stocks": len(codes), "processed": total_processed, "errors": total_errors}
    except Exception as e:
        logger.error(f"[스케줄러] AI 공시 분석 실패: {e}", exc_info=True)
        _save_log("scheduler_ai_disclosure", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_supply_demand_batch() -> dict:
    """수급 분석 배치 작업 (관심종목 + 분석점수 상위)"""
    started_at = datetime.now()
    logger.info("[스케줄러] 수급 분석 배치 시작")
    try:
        from app.services.supply_demand_analysis_service import run_supply_demand_batch
        result = run_supply_demand_batch(limit=80)
        status = result.get("status", "unknown")
        msg = (
            f"수급 배치 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_supply_demand", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 수급 분석 배치 실패: {e}", exc_info=True)
        _save_log("scheduler_supply_demand", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_fundamental_batch() -> dict:
    """펀더멘털 배치 분석 작업 (관심종목 + 분석점수 상위)"""
    started_at = datetime.now()
    logger.info("[스케줄러] 펀더멘털 배치 시작")
    try:
        from app.services.fundamental_analysis_service import run_fundamental_batch
        result = run_fundamental_batch(limit=80)
        status = result.get("status", "unknown")
        msg = (
            f"펀더멘털 배치 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_fundamental", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 펀더멘털 배치 실패: {e}", exc_info=True)
        _save_log("scheduler_fundamental", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_news_sentiment_batch() -> dict:
    """뉴스 감성 배치 분석 작업 (관심종목 + 분석점수 상위)"""
    started_at = datetime.now()
    logger.info("[스케줄러] 뉴스 감성 배치 시작")
    try:
        from app.services.news_analysis_service import run_news_batch
        result = run_news_batch(limit=80)
        status = result.get("status", "unknown")
        msg = (
            f"뉴스 감성 배치 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_news_sentiment", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 뉴스 감성 배치 실패: {e}", exc_info=True)
        _save_log("scheduler_news_sentiment", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_chart_pattern_batch() -> dict:
    """차트 패턴 배치 분석 작업 (관심종목 + 분석점수 상위)"""
    started_at = datetime.now()
    logger.info("[스케줄러] 차트 패턴 배치 시작")
    try:
        from app.services.chart_pattern_analysis_service import run_chart_pattern_batch
        result = run_chart_pattern_batch(limit=80)
        status = result.get("status", "unknown")
        msg = (
            f"차트 패턴 배치 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_chart_pattern", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 차트 패턴 배치 실패: {e}", exc_info=True)
        _save_log("scheduler_chart_pattern", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_risk_batch() -> dict:
    """위험도 배치 분석 작업 (관심종목 + 분석점수 상위)"""
    started_at = datetime.now()
    logger.info("[스케줄러] 위험도 배치 시작")
    try:
        from app.services.risk_analysis_service import run_risk_batch
        result = run_risk_batch(limit=80)
        status = result.get("status", "unknown")
        msg = (
            f"위험도 배치 완료: 성공={result.get('success', 0)}, "
            f"스킵={result.get('skipped', 0)}, 오류={result.get('errors', 0)}"
        )
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_risk", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 위험도 배치 실패: {e}", exc_info=True)
        _save_log("scheduler_risk", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_advanced_market_ai() -> dict:
    """AI 종합 시장 분석 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] AI 종합 시장 분석 시작")
    try:
        from app.services.advanced_market_ai_service import generate_advanced_market_ai
        result = generate_advanced_market_ai()
        status = result.get("status", "unknown")
        msg = f"AI 종합 시장 분석 완료: {result.get('report_date', '-')} ({status})"
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_advanced_market_ai", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] AI 종합 시장 분석 실패: {e}", exc_info=True)
        _save_log("scheduler_advanced_market_ai", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_theme_analysis() -> dict:
    """테마 강세/약세 분석 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] 테마 분석 시작")
    try:
        from app.services.theme_analysis_service import run_theme_analysis
        result = run_theme_analysis()
        status = result.get("status", "unknown")
        msg = f"테마 분석 완료: 테마={result.get('themes', 0)}개, 오류={result.get('errors', 0)}개"
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_theme_analysis", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] 테마 분석 실패: {e}", exc_info=True)
        _save_log("scheduler_theme_analysis", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


def job_ai_market_report() -> dict:
    """AI 시장 리포트 생성 작업"""
    started_at = datetime.now()
    logger.info("[스케줄러] AI 시장 리포트 생성 시작")
    try:
        from app.services.market_report_ai_service import generate_market_report
        result = generate_market_report()
        status = result.get("status", "unknown")
        msg = f"AI 시장 리포트 생성 완료: {result.get('report_date', '-')}"
        logger.info(f"[스케줄러] {msg}")
        _save_log("scheduler_ai_market_report", status, msg, started_at)
        return result
    except Exception as e:
        logger.error(f"[스케줄러] AI 시장 리포트 생성 실패: {e}", exc_info=True)
        _save_log("scheduler_ai_market_report", "error", str(e), started_at)
        return {"status": "error", "message": str(e)}


# ── 일일 파이프라인 ──────────────────────────────────────────────

def run_daily_pipeline() -> dict:
    """
    일일 전체 파이프라인 순차 실행 (8단계).
    각 단계 실패 시 다음 단계는 계속 실행 — 서버 종료 없음.
    """
    pipeline_start = datetime.now()
    logger.info("=" * 50)
    logger.info("[스케줄러] 일일 파이프라인 시작")
    results = {}

    # 1. 종목 리스트 수집
    r1 = job_collect_stocks()
    results["collect_stocks"] = r1
    if r1.get("status") == "error":
        logger.warning("[스케줄러] 종목 수집 실패 - 기존 데이터로 계속 진행")

    # 2. 가격 데이터 수집
    r2 = job_collect_prices(days=1)
    results["collect_prices"] = r2
    if r2.get("status") == "error":
        logger.warning("[스케줄러] 가격 수집 실패 - 기존 데이터로 분석 진행")

    # 3. 분석 실행
    r3 = job_run_analysis()
    results["analysis"] = r3
    if r3.get("status") == "error":
        logger.warning("[스케줄러] 분석 실패 - 이하 단계는 이전 결과로 진행")

    # 4. 관심종목 자동 선정
    r4 = job_auto_watchlist()
    results["auto_watchlist"] = r4
    if r4.get("status") == "error":
        logger.warning("[스케줄러] 관심종목 자동 선정 실패 - 계속 진행")

    # 5. AI 종목 분석
    r5 = job_ai_stock_analysis(limit=30)
    results["ai_stock"] = r5
    if r5.get("status") == "error":
        logger.warning("[스케줄러] AI 종목 분석 실패 - 계속 진행")

    # 6. AI 공시 분석
    r6 = job_ai_disclosure_analysis()
    results["ai_disclosure"] = r6
    if r6.get("status") == "error":
        logger.warning("[스케줄러] AI 공시 분석 실패 - 계속 진행")

    # 7. AI 시장 리포트 생성
    r7 = job_ai_market_report()
    results["ai_market_report"] = r7
    if r7.get("status") == "error":
        logger.warning("[스케줄러] AI 시장 리포트 생성 실패 - 리포트 저장 계속 진행")

    # 8. 수급 분석 배치
    r8 = job_supply_demand_batch()
    results["supply_demand"] = r8
    if r8.get("status") == "error":
        logger.warning("[스케줄러] 수급 분석 배치 실패 - 계속 진행")

    # 9. 펀더멘털 배치 분석
    r9 = job_fundamental_batch()
    results["fundamental"] = r9
    if r9.get("status") == "error":
        logger.warning("[스케줄러] 펀더멘털 배치 실패 - 계속 진행")

    # 10. 뉴스 감성 배치 분석
    r10 = job_news_sentiment_batch()
    results["news_sentiment"] = r10
    if r10.get("status") == "error":
        logger.warning("[스케줄러] 뉴스 감성 배치 실패 - 계속 진행")

    # 11. 테마 분석 실행
    r11_theme = job_theme_analysis()
    results["theme_analysis"] = r11_theme
    if r11_theme.get("status") == "error":
        logger.warning("[스케줄러] 테마 분석 실패 - 계속 진행")

    # 12. 리포트 저장
    r12 = job_generate_report()
    results["report"] = r12

    elapsed = (datetime.now() - pipeline_start).total_seconds()
    overall = "success" if all(
        r.get("status") not in ("error",) for r in results.values()
    ) else "partial"

    logger.info(f"[스케줄러] 일일 파이프라인 완료 ({elapsed:.1f}초) - {overall}")
    logger.info("=" * 50)

    _save_log(
        "scheduler_daily_pipeline",
        overall,
        f"elapsed={elapsed:.1f}s | " + " | ".join(
            f"{k}={v.get('status','?')}" for k, v in results.items()
        ),
        pipeline_start,
    )
    return {"status": overall, "elapsed_seconds": round(elapsed, 1), "steps": results}


def run_advanced_pipeline() -> dict:
    """
    고급 전체 파이프라인 순차 실행 (11단계).

    1. 종목 수집
    2. 가격 수집
    3. 분석 계산
    4. 수급 분석
    5. 뉴스 분석
    6. 실적 분석
    7. 차트 패턴 분석
    8. 테마 분석
    9. 위험도 분석
    10. AI 종합 시장 분석
    11. 리포트 저장

    각 단계 실패 시 다음 단계는 계속 실행 — 서버 종료 없음.
    """
    pipeline_start = datetime.now()
    logger.info("=" * 50)
    logger.info("[스케줄러] 고급 파이프라인 시작")
    results = {}

    # 1. 종목 수집
    r1 = job_collect_stocks()
    results["collect_stocks"] = r1
    if r1.get("status") == "error":
        logger.warning("[스케줄러] 종목 수집 실패 - 기존 데이터로 계속 진행")

    # 2. 가격 수집
    r2 = job_collect_prices(days=1)
    results["collect_prices"] = r2
    if r2.get("status") == "error":
        logger.warning("[스케줄러] 가격 수집 실패 - 기존 데이터로 분석 진행")

    # 3. 분석 계산
    r3 = job_run_analysis()
    results["analysis"] = r3
    if r3.get("status") == "error":
        logger.warning("[스케줄러] 분석 실패 - 이하 단계는 이전 결과로 진행")

    # 4. 수급 분석
    r4 = job_supply_demand_batch()
    results["supply_demand"] = r4
    if r4.get("status") == "error":
        logger.warning("[스케줄러] 수급 분석 실패 - 계속 진행")

    # 5. 뉴스 분석
    r5 = job_news_sentiment_batch()
    results["news_sentiment"] = r5
    if r5.get("status") == "error":
        logger.warning("[스케줄러] 뉴스 분석 실패 - 계속 진행")

    # 6. 실적 분석
    r6 = job_fundamental_batch()
    results["fundamental"] = r6
    if r6.get("status") == "error":
        logger.warning("[스케줄러] 실적 분석 실패 - 계속 진행")

    # 7. 차트 패턴 분석
    r7 = job_chart_pattern_batch()
    results["chart_pattern"] = r7
    if r7.get("status") == "error":
        logger.warning("[스케줄러] 차트 패턴 분석 실패 - 계속 진행")

    # 8. 테마 분석
    r8 = job_theme_analysis()
    results["theme_analysis"] = r8
    if r8.get("status") == "error":
        logger.warning("[스케줄러] 테마 분석 실패 - 계속 진행")

    # 9. 위험도 분석
    r9 = job_risk_batch()
    results["risk"] = r9
    if r9.get("status") == "error":
        logger.warning("[스케줄러] 위험도 분석 실패 - 계속 진행")

    # 10. AI 종합 시장 분석
    r10 = job_advanced_market_ai()
    results["advanced_market_ai"] = r10
    if r10.get("status") == "error":
        logger.warning("[스케줄러] AI 종합 시장 분석 실패 - 리포트 저장 계속 진행")

    # 11. 리포트 저장
    r11 = job_generate_report()
    results["report"] = r11

    elapsed = (datetime.now() - pipeline_start).total_seconds()
    overall = "success" if all(
        r.get("status") not in ("error",) for r in results.values()
    ) else "partial"

    logger.info(f"[스케줄러] 고급 파이프라인 완료 ({elapsed:.1f}초) - {overall}")
    logger.info("=" * 50)

    _save_log(
        "scheduler_advanced_pipeline",
        overall,
        f"elapsed={elapsed:.1f}s | " + " | ".join(
            f"{k}={v.get('status','?')}" for k, v in results.items()
        ),
        pipeline_start,
    )
    return {"status": overall, "elapsed_seconds": round(elapsed, 1), "steps": results}


def run_ai_pipeline() -> dict:
    """
    AI 분석 파이프라인 단독 실행 (3단계).
    분석 데이터가 이미 있을 때 AI 단계만 재실행하는 용도.
    각 단계 실패 시 다음 단계는 계속 실행 — 서버 종료 없음.
    """
    pipeline_start = datetime.now()
    logger.info("=" * 50)
    logger.info("[스케줄러] AI 파이프라인 시작")
    results = {}

    # 1. AI 종목 분석
    r1 = job_ai_stock_analysis(limit=30)
    results["ai_stock"] = r1
    if r1.get("status") == "error":
        logger.warning("[스케줄러] AI 종목 분석 실패 - 공시/리포트 단계는 계속 진행")

    # 2. AI 공시 분석
    r2 = job_ai_disclosure_analysis()
    results["ai_disclosure"] = r2
    if r2.get("status") == "error":
        logger.warning("[스케줄러] AI 공시 분석 실패 - AI 시장 리포트는 계속 진행")

    # 3. AI 시장 리포트 생성
    r3 = job_ai_market_report()
    results["ai_market_report"] = r3

    elapsed = (datetime.now() - pipeline_start).total_seconds()
    overall = "success" if all(
        r.get("status") not in ("error",) for r in results.values()
    ) else "partial"

    logger.info(f"[스케줄러] AI 파이프라인 완료 ({elapsed:.1f}초) - {overall}")
    logger.info("=" * 50)

    _save_log(
        "scheduler_ai_pipeline",
        overall,
        f"elapsed={elapsed:.1f}s | " + " | ".join(
            f"{k}={v.get('status','?')}" for k, v in results.items()
        ),
        pipeline_start,
    )
    return {"status": overall, "elapsed_seconds": round(elapsed, 1), "steps": results}


# ── 스케줄러 생명주기 ────────────────────────────────────────────

def get_scheduler_status() -> dict:
    """스케줄러 상태와 등록된 잡 목록을 반환합니다."""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(next_run) if next_run else None,
            "trigger": str(job.trigger),
        })
    return {"running": _scheduler.running, "jobs": jobs}


def start_scheduler() -> None:
    """APScheduler를 시작하고 일일 파이프라인 잡을 등록합니다."""
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info("[스케줄러] 이미 실행 중입니다.")
        return

    report_time = settings.REPORT_TIME  # 기본 "18:30"
    try:
        hour, minute = report_time.split(":")
        hour, minute = int(hour), int(minute)
    except (ValueError, AttributeError):
        logger.warning(f"[스케줄러] REPORT_TIME 파싱 실패 ({report_time!r}), 기본값 18:30 사용")
        hour, minute = 18, 30

    # AI 파이프라인은 메인 파이프라인보다 30분 뒤 실행
    ai_minute = minute + 30
    ai_hour   = hour + ai_minute // 60
    ai_minute = ai_minute % 60
    ai_hour   = ai_hour % 24

    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    # 파이프라인 A: 매일 REPORT_TIME — 수집 → 분석 → AI → 리포트
    _scheduler.add_job(
        run_daily_pipeline,
        trigger=CronTrigger(hour=hour, minute=minute, timezone="Asia/Seoul"),
        id="daily_pipeline",
        name=f"일일 전체 파이프라인 ({hour:02d}:{minute:02d} KST)",
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,
    )

    # 파이프라인 B: REPORT_TIME + 30분 — AI 분석 단독 (데이터 수집 없이 재실행용)
    _scheduler.add_job(
        run_ai_pipeline,
        trigger=CronTrigger(hour=ai_hour, minute=ai_minute, timezone="Asia/Seoul"),
        id="ai_pipeline",
        name=f"AI 분석 파이프라인 ({ai_hour:02d}:{ai_minute:02d} KST)",
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        f"[스케줄러] 시작 완료 — "
        f"전체 파이프라인 {hour:02d}:{minute:02d} KST / "
        f"AI 파이프라인 {ai_hour:02d}:{ai_minute:02d} KST"
    )


def stop_scheduler() -> None:
    """스케줄러를 안전하게 종료합니다."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[스케줄러] 종료 완료")
    _scheduler = None
