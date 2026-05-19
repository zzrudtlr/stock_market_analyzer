"""
분석 서비스 - DB의 시세 데이터를 읽어 강세/약세 점수를 계산하고 저장합니다.
"""
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.analyzers.score_calculator import calculate_metrics, calculate_scores, determine_signal
from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.price import StockDailyPrice
from app.models.stock import Stock
from app.services.price_service import get_market_return_20d

logger = logging.getLogger(__name__)

_BULK_DAYS = 200       # 캘린더 일수 기준 (약 130 거래일 커버)
_WORKERS   = 16        # CPU-bound 계산용 스레드 수
_COMMIT_CHUNK = 500    # 한 번에 커밋할 행 수


def _bulk_load_prices(session, stock_codes: list[str]) -> dict[str, pd.DataFrame]:
    """전 종목 가격 데이터를 단일 쿼리로 로드해 종목코드별 DataFrame dict 반환."""
    cutoff = date.today() - timedelta(days=_BULK_DAYS)
    q = (
        select(StockDailyPrice)
        .where(
            StockDailyPrice.stock_code.in_(stock_codes),
            StockDailyPrice.trade_date >= cutoff,
        )
        .order_by(StockDailyPrice.stock_code, StockDailyPrice.trade_date)
    )
    rows = session.execute(q).scalars().all()

    grouped: dict[str, list] = defaultdict(list)
    for r in rows:
        grouped[r.stock_code].append({
            "trade_date":   r.trade_date,
            "close_price":  r.close_price,
            "volume":       r.volume,
            "open_price":   r.open_price,
            "high_price":   r.high_price,
            "low_price":    r.low_price,
            "change_rate":  float(r.change_rate) if r.change_rate is not None else None,
        })

    return {
        code: pd.DataFrame(records)
        for code, records in grouped.items()
    }


def _calc_one(stock_code: str, stock_market: str, prices_df: pd.DataFrame,
              ks11_ret, kq11_ret, target_date: date) -> Optional[dict]:
    """단일 종목 지표·점수 계산 (스레드 안전, DB 접근 없음)."""
    try:
        if prices_df.empty or len(prices_df) < 5:
            return None
        metrics = calculate_metrics(prices_df)
        if metrics is None:
            return None
        market_ret = ks11_ret if stock_market == "KOSPI" else kq11_ret
        scores = calculate_scores(metrics, market_return_20d=market_ret)
        signal, reason = determine_signal(
            scores["bullish_score"], scores["bearish_score"], metrics, scores
        )
        return {
            "stock_code":       stock_code,
            "analysis_date":    target_date,
            "daily_return":     metrics.get("daily_return"),
            "return_5d":        metrics.get("return_5d"),
            "return_20d":       metrics.get("return_20d"),
            "return_60d":       metrics.get("return_60d"),
            "volume_ratio_5d":  metrics.get("volume_ratio_5d"),
            "volume_ratio_20d": metrics.get("volume_ratio_20d"),
            "ma5":              metrics.get("ma5"),
            "ma20":             metrics.get("ma20"),
            "ma60":             metrics.get("ma60"),
            "ma120":            metrics.get("ma120"),
            "rsi14":            metrics.get("rsi14"),
            "volatility_20d":   metrics.get("volatility_20d"),
            "relative_strength": scores.get("relative_strength"),
            "momentum_score":   scores.get("momentum_score"),
            "volume_score":     scores.get("volume_score"),
            "trend_score":      scores.get("trend_score"),
            "risk_score":       scores.get("risk_score"),
            "disclosure_score": scores.get("disclosure_score"),
            "bullish_score":    scores.get("bullish_score"),
            "bearish_score":    scores.get("bearish_score"),
            "final_signal":     signal,
            "signal_reason":    reason,
        }
    except Exception as e:
        logger.error(f"[{stock_code}] 계산 실패: {e}")
        return None


def _upsert_rows(session, rows: list[dict]) -> None:
    """rows를 stock_analysis_results에 bulk upsert."""
    for row in rows:
        stmt = mysql_insert(StockAnalysisResult).values(**row)
        stmt = stmt.on_duplicate_key_update(
            daily_return=stmt.inserted.daily_return,
            return_5d=stmt.inserted.return_5d,
            return_20d=stmt.inserted.return_20d,
            return_60d=stmt.inserted.return_60d,
            volume_ratio_5d=stmt.inserted.volume_ratio_5d,
            volume_ratio_20d=stmt.inserted.volume_ratio_20d,
            ma5=stmt.inserted.ma5,
            ma20=stmt.inserted.ma20,
            ma60=stmt.inserted.ma60,
            ma120=stmt.inserted.ma120,
            rsi14=stmt.inserted.rsi14,
            volatility_20d=stmt.inserted.volatility_20d,
            relative_strength=stmt.inserted.relative_strength,
            momentum_score=stmt.inserted.momentum_score,
            volume_score=stmt.inserted.volume_score,
            trend_score=stmt.inserted.trend_score,
            risk_score=stmt.inserted.risk_score,
            disclosure_score=stmt.inserted.disclosure_score,
            bullish_score=stmt.inserted.bullish_score,
            bearish_score=stmt.inserted.bearish_score,
            final_signal=stmt.inserted.final_signal,
            signal_reason=stmt.inserted.signal_reason,
        )
        session.execute(stmt)


def run_analysis(
    analysis_date: Optional[date] = None,
    market: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    모든 활성 종목에 대해 분석을 실행하고 stock_analysis_results에 저장합니다.
    - 가격 데이터를 단일 bulk 쿼리로 로드
    - 지표/점수 계산은 ThreadPoolExecutor로 병렬화
    """
    target_date = analysis_date or date.today()
    session = get_db_session()
    success = 0
    skipped = 0
    errors = 0

    try:
        q = select(Stock.stock_code, Stock.market).where(Stock.is_active == 1)
        if market:
            q = q.where(Stock.market == market)
        if limit:
            q = q.limit(limit)
        stocks = session.execute(q).all()

        if not stocks:
            return {"status": "no_stocks", "message": "분석할 종목이 없습니다. 먼저 종목 수집을 실행하세요."}

        ks11_return = get_market_return_20d("KS11")
        kq11_return = get_market_return_20d("KQ11")

        stock_codes = [s.stock_code for s in stocks]
        logger.info(f"분석 시작: {len(stocks)} 종목, 날짜={target_date} — bulk 가격 로드 중...")

        price_map = _bulk_load_prices(session, stock_codes)
        logger.info(f"가격 로드 완료: {len(price_map)} 종목 데이터 확보")

        # 병렬 계산
        futures = {}
        with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
            for stock_code, stock_market in stocks:
                df = price_map.get(stock_code, pd.DataFrame())
                futures[executor.submit(
                    _calc_one, stock_code, stock_market, df,
                    ks11_return, kq11_return, target_date
                )] = stock_code

        # 결과 수집 및 청크 단위 저장
        pending: list[dict] = []
        for fut in as_completed(futures):
            result = fut.result()
            if result is None:
                skipped += 1
                continue
            pending.append(result)
            if len(pending) >= _COMMIT_CHUNK:
                _upsert_rows(session, pending)
                session.commit()
                success += len(pending)
                logger.info(f"진행: {success}/{len(stocks)}")
                pending.clear()

        if pending:
            _upsert_rows(session, pending)
            session.commit()
            success += len(pending)

        logger.info(f"분석 완료: 성공={success}, 스킵={skipped}, 에러={errors}")
        return {
            "status": "success",
            "date": str(target_date),
            "success": success,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        logger.error(f"run_analysis 실패: {e}")
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def get_high_volume_stocks(
    analysis_date: Optional[date] = None,
    market: Optional[str] = None,
    min_ratio: float = 2.0,
    limit: int = 20,
) -> list[dict]:
    """5일 평균 대비 거래량 급증 종목을 반환합니다."""
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        q = (
            select(StockAnalysisResult, Stock.stock_name, Stock.market, Stock.sector)
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            .where(
                StockAnalysisResult.analysis_date == target_date,
                StockAnalysisResult.volume_ratio_5d >= min_ratio,
            )
        )
        if market:
            q = q.where(Stock.market == market)
        q = q.order_by(StockAnalysisResult.volume_ratio_5d.desc()).limit(limit)
        rows = session.execute(q).all()
        return [
            {
                "stock_code": r.StockAnalysisResult.stock_code,
                "stock_name": r.stock_name,
                "market": r.market,
                "sector": r.sector,
                "volume_ratio_5d": float(r.StockAnalysisResult.volume_ratio_5d) if r.StockAnalysisResult.volume_ratio_5d else None,
                "volume_ratio_20d": float(r.StockAnalysisResult.volume_ratio_20d) if r.StockAnalysisResult.volume_ratio_20d else None,
                "daily_return": float(r.StockAnalysisResult.daily_return) if r.StockAnalysisResult.daily_return else None,
                "final_signal": r.StockAnalysisResult.final_signal,
                "bullish_score": float(r.StockAnalysisResult.bullish_score) if r.StockAnalysisResult.bullish_score else None,
            }
            for r in rows
        ]
    finally:
        session.close()


def get_analysis_results(
    analysis_date: Optional[date] = None,
    signal: Optional[str] = None,
    order_by: str = "bullish_score",
    limit: int = 50,
    market: Optional[str] = None,
) -> list[dict]:
    """분석 결과를 조회합니다."""
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        q = (
            select(StockAnalysisResult, Stock.stock_name, Stock.market, Stock.sector)
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            .where(StockAnalysisResult.analysis_date == target_date)
        )
        if signal:
            q = q.where(StockAnalysisResult.final_signal == signal)
        if market:
            q = q.where(Stock.market == market)

        if order_by == "bearish_score":
            q = q.order_by(StockAnalysisResult.bearish_score.desc())
        else:
            q = q.order_by(StockAnalysisResult.bullish_score.desc())

        q = q.limit(limit)
        rows = session.execute(q).all()

        return [
            {
                "stock_code": r.StockAnalysisResult.stock_code,
                "stock_name": r.stock_name,
                "market": r.market,
                "sector": r.sector,
                "analysis_date": str(r.StockAnalysisResult.analysis_date),
                "daily_return": float(r.StockAnalysisResult.daily_return) if r.StockAnalysisResult.daily_return else None,
                "return_5d": float(r.StockAnalysisResult.return_5d) if r.StockAnalysisResult.return_5d else None,
                "return_20d": float(r.StockAnalysisResult.return_20d) if r.StockAnalysisResult.return_20d else None,
                "volume_ratio_5d": float(r.StockAnalysisResult.volume_ratio_5d) if r.StockAnalysisResult.volume_ratio_5d else None,
                "rsi14": float(r.StockAnalysisResult.rsi14) if r.StockAnalysisResult.rsi14 else None,
                "bullish_score": float(r.StockAnalysisResult.bullish_score) if r.StockAnalysisResult.bullish_score else None,
                "bearish_score": float(r.StockAnalysisResult.bearish_score) if r.StockAnalysisResult.bearish_score else None,
                "final_signal": r.StockAnalysisResult.final_signal,
                "signal_reason": r.StockAnalysisResult.signal_reason,
            }
            for r in rows
        ]
    finally:
        session.close()


def get_analysis_summary(analysis_date: Optional[date] = None, market: Optional[str] = None) -> dict:
    """시그널별 종목 수 요약을 반환합니다."""
    from sqlalchemy import func as sqlfunc
    target_date = analysis_date or date.today()
    session = get_db_session()
    try:
        q = (
            select(StockAnalysisResult.final_signal, sqlfunc.count().label("cnt"))
            .where(StockAnalysisResult.analysis_date == target_date)
        )
        if market:
            q = q.join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            q = q.where(Stock.market == market)
        q = q.group_by(StockAnalysisResult.final_signal)
        rows = session.execute(q).all()
        result = {r.final_signal: r.cnt for r in rows}
        result["total"] = sum(result.values())
        result["date"] = str(target_date)
        return result
    finally:
        session.close()
