"""
KRX 데이터 수집기 - pykrx를 사용한 일별 시세 수집
Windows 환경: PYTHONUTF8=1 설정 필요 (서버 재시작 자동 적용)
"""
import logging
import os
import sys
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models.collector_log import CollectorLog
from app.models.price import StockDailyPrice
from app.utils.date_utils import format_date_krx, get_start_date
from app.utils.retry import retry

logger = logging.getLogger(__name__)

# pykrx 컬럼 위치 매핑 (버전/인코딩 무관하게 위치로 접근)
# get_market_ohlcv_by_ticker 반환 순서: 시가 고가 저가 종가 거래량 거래대금 시가총액 등락률
_KRX_COLS = ["open_price", "high_price", "low_price", "close_price",
             "volume", "trading_value", "market_cap", "change_rate"]


def _normalize_krx_df(df: pd.DataFrame) -> pd.DataFrame:
    """pykrx 한글 컬럼명 인코딩 문제 방지 - 위치 기반 영문명으로 교체"""
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = _KRX_COLS[:len(df.columns)]
    return df


def _save_log(
    session: Session,
    name: str,
    target_date: Optional[date],
    status: str,
    message: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    try:
        log = CollectorLog(
            collector_name=name,
            target_date=target_date,
            status=status,
            message=message[:2000] if message else None,
            started_at=started_at,
            finished_at=finished_at,
        )
        session.add(log)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to save collector log: {e}")
        session.rollback()


def _fetch_krx_ohlcv_raw(krx_date: str, market: str) -> pd.DataFrame:
    """
    pykrx로 일별 전종목 OHLCV를 수집합니다.
    인코딩 오류 방지를 위해 컬럼 선택 전 raw DataFrame을 가로챕니다.
    """
    from pykrx import stock as krx_stock

    # pykrx 내부에서 한글 컬럼명으로 df[...] 선택 시 에러가 발생하는 경우 대비:
    # MKD80037().fetch() 직접 호출로 raw DataFrame 획득
    try:
        from pykrx.stock.market.core import MKD80037
        inst = MKD80037()
        df_raw = inst.fetch(krx_date, krx_date, market)
        if df_raw is not None and not df_raw.empty:
            return _normalize_krx_df(df_raw)
    except Exception as inner_e:
        logger.debug(f"MKD80037 직접 호출 실패, 표준 API 시도: {inner_e}")

    # 표준 API fallback
    df = krx_stock.get_market_ohlcv_by_ticker(krx_date, market=market)
    return _normalize_krx_df(df)


@retry(max_attempts=3, delay=3.0)
def _fetch_krx_ohlcv(krx_date: str, market: str) -> pd.DataFrame:
    return _fetch_krx_ohlcv_raw(krx_date, market)


def _upsert_prices(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = mysql_insert(StockDailyPrice).values(rows)
    stmt = stmt.on_duplicate_key_update(
        open_price=stmt.inserted.open_price,
        high_price=stmt.inserted.high_price,
        low_price=stmt.inserted.low_price,
        close_price=stmt.inserted.close_price,
        change_rate=stmt.inserted.change_rate,
        volume=stmt.inserted.volume,
        trading_value=stmt.inserted.trading_value,
        market_cap=stmt.inserted.market_cap,
    )
    session.execute(stmt)
    session.commit()
    return len(rows)


def collect_prices_by_date(target_date: date) -> dict:
    """단일 날짜의 KOSPI + KOSDAQ 전체 종목 시세를 수집합니다."""
    started_at = datetime.now()
    session = get_db_session()
    krx_date = format_date_krx(target_date)
    total = 0

    try:
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                df = _fetch_krx_ohlcv(krx_date, market)
                if df is None or df.empty:
                    logger.warning(f"No data from pykrx for {market} on {krx_date}")
                    continue

                rows = []
                for ticker, row in df.iterrows():
                    try:
                        close = int(row.get("close_price", 0) or 0)
                        if close <= 0:
                            continue

                        change_rate_raw = row.get("change_rate")
                        change_rate = float(change_rate_raw) if pd.notna(change_rate_raw) else None

                        market_cap = None
                        mc_raw = row.get("market_cap")
                        if mc_raw is not None and pd.notna(mc_raw):
                            try:
                                market_cap = int(mc_raw)
                            except (ValueError, OverflowError):
                                pass

                        trading_value = None
                        tv_raw = row.get("trading_value")
                        if tv_raw is not None and pd.notna(tv_raw):
                            try:
                                trading_value = int(tv_raw)
                            except (ValueError, OverflowError):
                                pass

                        rows.append({
                            "stock_code": str(ticker),
                            "trade_date": target_date,
                            "open_price": int(row.get("open_price", 0) or 0) or None,
                            "high_price": int(row.get("high_price", 0) or 0) or None,
                            "low_price": int(row.get("low_price", 0) or 0) or None,
                            "close_price": close,
                            "change_price": None,
                            "change_rate": change_rate,
                            "volume": int(row.get("volume", 0) or 0) or None,
                            "trading_value": trading_value,
                            "market_cap": market_cap,
                        })
                    except Exception as e:
                        logger.debug(f"Skip ticker {ticker}: {e}")

                saved = _upsert_prices(session, rows)
                total += saved
                logger.info(f"[{market}] {krx_date}: {saved} 종목 저장")

            except Exception as e:
                logger.error(f"[{market}] {krx_date} 수집 실패: {e}")
                _save_log(session, f"krx_price_{market}", target_date, "error", str(e), started_at, datetime.now())

        _save_log(session, "krx_price_bulk", target_date, "success", f"{total}건 저장", started_at, datetime.now())
        return {"status": "success", "date": str(target_date), "count": total}

    except Exception as e:
        logger.error(f"collect_prices_by_date 실패: {e}")
        _save_log(session, "krx_price_bulk", target_date, "error", str(e), started_at, datetime.now())
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def collect_prices_bulk(days: int = 60) -> dict:
    """최근 N일치 시세를 날짜별로 순차 수집합니다."""
    from datetime import timedelta
    end = date.today()
    start = get_start_date(days, end)
    current = start
    results = []

    while current <= end:
        if current.weekday() < 5:
            result = collect_prices_by_date(current)
            results.append(result)
        current += timedelta(days=1)

    success = sum(1 for r in results if r.get("status") == "success")
    total_count = sum(r.get("count", 0) for r in results if r.get("status") == "success")
    return {"status": "done", "days_processed": success, "total_records": total_count}
