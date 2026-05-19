"""
FinanceDataReader 기반 수집기
- 종목 상장 정보 (sector/industry 포함)
- 시장 지수 데이터 (KOSPI, KOSDAQ)
- 개별 종목 역사 시세 (fallback용)
"""
import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models.collector_log import CollectorLog
from app.models.market import MarketIndex
from app.models.price import StockDailyPrice
from app.models.stock import Stock
from app.utils.date_utils import get_start_date
from app.utils.retry import retry

logger = logging.getLogger(__name__)

MARKET_INDEX_MAP = {
    "KS11": ("KOSPI", "코스피 지수"),
    "KQ11": ("KOSDAQ", "코스닥 지수"),
}


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


@retry(max_attempts=3, delay=3.0)
def _fetch_stock_listing(market: str) -> pd.DataFrame:
    import FinanceDataReader as fdr
    return fdr.StockListing(market)


@retry(max_attempts=3, delay=3.0)
def _fetch_data_reader(symbol: str, start: str, end: str) -> pd.DataFrame:
    import FinanceDataReader as fdr
    return fdr.DataReader(symbol, start, end)


def collect_stock_list() -> dict:
    """KOSPI + KOSDAQ 종목 리스트를 수집해 stocks 테이블에 저장합니다."""
    started_at = datetime.now()
    session = get_db_session()
    total = 0

    try:
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                df = _fetch_stock_listing(market)
                logger.info(f"FDR {market} listing: {len(df)} rows, cols={df.columns.tolist()}")

                # 컬럼명 정규화 (FDR 버전별 차이 대응)
                col_map = {
                    "Symbol": "stock_code", "Code": "stock_code",
                    "Name": "stock_name",
                    "Sector": "sector",
                    "Industry": "industry",
                    "ListingDate": "listing_date", "IPODate": "listing_date",
                    "Market": "market_col",
                }
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

                if "stock_code" not in df.columns:
                    logger.error(f"stock_code 컬럼 없음: {df.columns.tolist()}")
                    continue

                rows = []
                for _, row in df.iterrows():
                    code = str(row.get("stock_code", "")).strip()
                    name = str(row.get("stock_name", "")).strip()
                    if not code or not name or code == "nan":
                        continue

                    listing_date = None
                    ld = row.get("listing_date")
                    if ld is not None and pd.notna(ld):
                        try:
                            listing_date = pd.to_datetime(ld).date()
                        except Exception:
                            pass

                    sector = row.get("sector")
                    industry = row.get("industry")

                    rows.append({
                        "market": market,
                        "stock_code": code,
                        "stock_name": name,
                        "sector": str(sector) if sector is not None and pd.notna(sector) else None,
                        "industry": str(industry) if industry is not None and pd.notna(industry) else None,
                        "listing_date": listing_date,
                        "is_active": 1,
                    })

                if rows:
                    stmt = mysql_insert(Stock).values(rows)
                    stmt = stmt.on_duplicate_key_update(
                        market=stmt.inserted.market,
                        stock_name=stmt.inserted.stock_name,
                        sector=stmt.inserted.sector,
                        industry=stmt.inserted.industry,
                        listing_date=stmt.inserted.listing_date,
                        is_active=1,
                    )
                    session.execute(stmt)
                    session.commit()
                    total += len(rows)
                    logger.info(f"[{market}] {len(rows)} 종목 저장")

            except Exception as e:
                logger.error(f"[{market}] 종목 리스트 수집 실패: {e}")
                session.rollback()
                _save_log(session, f"fdr_stock_list_{market}", date.today(), "error", str(e), started_at, datetime.now())

        _save_log(session, "fdr_stock_list", date.today(), "success", f"{total} 종목 저장", started_at, datetime.now())
        return {"status": "success", "count": total}

    except Exception as e:
        logger.error(f"collect_stock_list 실패: {e}")
        _save_log(session, "fdr_stock_list", date.today(), "error", str(e), started_at, datetime.now())
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def collect_market_indices(days: int = 60) -> dict:
    """KOSPI, KOSDAQ 지수 데이터를 수집해 market_indices 테이블에 저장합니다."""
    started_at = datetime.now()
    session = get_db_session()
    end = date.today()
    start = get_start_date(days, end)
    total = 0

    try:
        for index_code, (index_name_en, index_name) in MARKET_INDEX_MAP.items():
            try:
                df = _fetch_data_reader(index_code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                if df is None or df.empty:
                    logger.warning(f"No data for {index_code}")
                    continue

                df = df.reset_index()
                # FDR 컬럼 정규화
                df = df.rename(columns={
                    "Date": "trade_date",
                    "Close": "close_value",
                    "Change": "change_rate",
                    "Volume": "volume",
                })

                rows = []
                prev_close = None
                for _, row in df.iterrows():
                    trade_date = pd.to_datetime(row["trade_date"]).date()
                    close_val = float(row.get("close_value", 0) or 0)
                    if close_val <= 0:
                        prev_close = close_val
                        continue

                    change_rate = float(row.get("change_rate", 0) or 0) * 100
                    change_value = None
                    if prev_close and prev_close > 0:
                        change_value = close_val - prev_close

                    vol_raw = row.get("volume")
                    volume = int(vol_raw) if vol_raw is not None and pd.notna(vol_raw) else None

                    rows.append({
                        "index_code": index_code,
                        "index_name": index_name,
                        "trade_date": trade_date,
                        "close_value": close_val,
                        "change_value": change_value,
                        "change_rate": change_rate,
                        "volume": volume,
                        "trading_value": None,
                    })
                    prev_close = close_val

                if rows:
                    stmt = mysql_insert(MarketIndex).values(rows)
                    stmt = stmt.on_duplicate_key_update(
                        index_name=stmt.inserted.index_name,
                        close_value=stmt.inserted.close_value,
                        change_value=stmt.inserted.change_value,
                        change_rate=stmt.inserted.change_rate,
                        volume=stmt.inserted.volume,
                    )
                    session.execute(stmt)
                    session.commit()
                    total += len(rows)
                    logger.info(f"[{index_code}] {len(rows)}일 저장")

            except Exception as e:
                logger.error(f"[{index_code}] 지수 수집 실패: {e}")
                session.rollback()

        _save_log(session, "fdr_market_index", date.today(), "success", f"{total}건 저장", started_at, datetime.now())
        return {"status": "success", "count": total}

    except Exception as e:
        logger.error(f"collect_market_indices 실패: {e}")
        _save_log(session, "fdr_market_index", date.today(), "error", str(e), started_at, datetime.now())
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def collect_prices_bulk_fdr(days: int = 60, limit: Optional[int] = None) -> dict:
    """FDR을 이용해 전체 활성 종목의 역사 시세를 수집합니다 (pykrx 대체)."""
    from sqlalchemy import select as sa_select
    started_at = datetime.now()
    session = get_db_session()
    try:
        q = sa_select(Stock.stock_code).where(Stock.is_active == 1)
        if limit:
            q = q.limit(limit)
        codes = [r[0] for r in session.execute(q).all()]
    finally:
        session.close()

    if not codes:
        return {"status": "no_stocks", "message": "활성 종목 없음. 먼저 종목 수집 실행 필요"}

    success = 0
    errors = 0
    logger.info(f"FDR 시세 수집 시작: {len(codes)}종목 / {days}일")

    for i, code in enumerate(codes):
        result = collect_stock_prices_fdr(code, days)
        if result.get("status") == "success":
            success += 1
        else:
            errors += 1
        if (i + 1) % 100 == 0:
            logger.info(f"FDR 수집 진행: {i+1}/{len(codes)} (성공={success}, 에러={errors})")

    logger.info(f"FDR 시세 수집 완료: 성공={success}, 에러={errors}")
    return {"status": "done", "total": len(codes), "success": success, "errors": errors}


def collect_stock_prices_fdr(stock_code: str, days: int = 60) -> dict:
    """단일 종목의 역사 시세를 FDR로 수집합니다 (pykrx 대체/보완용)."""
    started_at = datetime.now()
    session = get_db_session()
    end = date.today()
    start = get_start_date(days, end)

    try:
        df = _fetch_data_reader(stock_code, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is None or df.empty:
            return {"status": "no_data", "stock_code": stock_code}

        df = df.reset_index()
        df = df.rename(columns={"Date": "trade_date", "Open": "Open", "High": "High",
                                 "Low": "Low", "Close": "Close", "Volume": "Volume", "Change": "Change"})

        rows = []
        prev_close = None
        for _, row in df.iterrows():
            trade_date = pd.to_datetime(row["trade_date"]).date()
            close = int(row.get("Close", 0) or 0)
            if close <= 0:
                prev_close = close
                continue

            change_rate_raw = row.get("Change")
            change_rate = float(change_rate_raw) * 100 if change_rate_raw is not None and pd.notna(change_rate_raw) else None
            change_price = int(close - prev_close) if prev_close else None

            vol_raw = row.get("Volume")
            volume = int(vol_raw) if vol_raw is not None and pd.notna(vol_raw) else None

            rows.append({
                "stock_code": stock_code,
                "trade_date": trade_date,
                "open_price": int(row.get("Open", 0) or 0) or None,
                "high_price": int(row.get("High", 0) or 0) or None,
                "low_price": int(row.get("Low", 0) or 0) or None,
                "close_price": close,
                "change_price": change_price,
                "change_rate": change_rate,
                "volume": volume,
                "trading_value": None,
                "market_cap": None,
            })
            prev_close = close

        if rows:
            stmt = mysql_insert(StockDailyPrice).values(rows)
            stmt = stmt.on_duplicate_key_update(
                open_price=stmt.inserted.open_price,
                high_price=stmt.inserted.high_price,
                low_price=stmt.inserted.low_price,
                close_price=stmt.inserted.close_price,
                change_price=stmt.inserted.change_price,
                change_rate=stmt.inserted.change_rate,
                volume=stmt.inserted.volume,
            )
            session.execute(stmt)
            session.commit()

        _save_log(session, "fdr_price", date.today(), "success", f"{stock_code}: {len(rows)}건", started_at, datetime.now())
        return {"status": "success", "stock_code": stock_code, "count": len(rows)}

    except Exception as e:
        logger.error(f"collect_stock_prices_fdr [{stock_code}] 실패: {e}")
        _save_log(session, "fdr_price", date.today(), "error", f"{stock_code}: {e}", started_at, datetime.now())
        return {"status": "error", "stock_code": stock_code, "message": str(e)}
    finally:
        session.close()
