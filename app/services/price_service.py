import logging
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models.price import StockDailyPrice
from app.models.market import MarketIndex

logger = logging.getLogger(__name__)


def get_price_history(
    stock_code: str,
    days: int = 120,
    session: Optional[Session] = None,
) -> pd.DataFrame:
    """DB에서 종목의 역사 시세를 pandas DataFrame으로 반환합니다."""
    own_session = session is None
    db = session or get_db_session()
    try:
        q = (
            select(StockDailyPrice)
            .where(StockDailyPrice.stock_code == stock_code)
            .order_by(StockDailyPrice.trade_date.desc())
            .limit(days)
        )
        rows = db.execute(q).scalars().all()
        if not rows:
            return pd.DataFrame()

        data = [
            {
                "trade_date": r.trade_date,
                "open_price": r.open_price,
                "high_price": r.high_price,
                "low_price": r.low_price,
                "close_price": r.close_price,
                "change_price": r.change_price,
                "change_rate": float(r.change_rate) if r.change_rate is not None else None,
                "volume": r.volume,
                "trading_value": r.trading_value,
                "market_cap": r.market_cap,
            }
            for r in rows
        ]
        df = pd.DataFrame(data).sort_values("trade_date").reset_index(drop=True)
        return df
    finally:
        if own_session:
            db.close()


def get_latest_prices(
    stock_codes: list[str],
    trade_date: Optional[date] = None,
    session: Optional[Session] = None,
) -> dict[str, dict]:
    """여러 종목의 최신 시세를 dict로 반환합니다."""
    own_session = session is None
    db = session or get_db_session()
    try:
        if trade_date:
            q = select(StockDailyPrice).where(
                and_(
                    StockDailyPrice.stock_code.in_(stock_codes),
                    StockDailyPrice.trade_date == trade_date,
                )
            )
        else:
            # 각 종목의 가장 최근 날짜
            from sqlalchemy import func as sqlfunc
            subq = (
                select(
                    StockDailyPrice.stock_code,
                    sqlfunc.max(StockDailyPrice.trade_date).label("max_date"),
                )
                .where(StockDailyPrice.stock_code.in_(stock_codes))
                .group_by(StockDailyPrice.stock_code)
                .subquery()
            )
            q = select(StockDailyPrice).join(
                subq,
                and_(
                    StockDailyPrice.stock_code == subq.c.stock_code,
                    StockDailyPrice.trade_date == subq.c.max_date,
                ),
            )

        rows = db.execute(q).scalars().all()
        return {
            r.stock_code: {
                "trade_date": str(r.trade_date),
                "close_price": r.close_price,
                "change_rate": float(r.change_rate) if r.change_rate is not None else None,
                "volume": r.volume,
            }
            for r in rows
        }
    finally:
        if own_session:
            db.close()


def get_market_return_20d(index_code: str = "KS11") -> Optional[float]:
    """KOSPI 20일 수익률을 반환합니다 (상대 강도 계산용)."""
    db = get_db_session()
    try:
        q = (
            select(MarketIndex.close_value)
            .where(MarketIndex.index_code == index_code)
            .order_by(MarketIndex.trade_date.desc())
            .limit(25)
        )
        rows = db.execute(q).scalars().all()
        if len(rows) < 21:
            return None
        # rows는 내림차순이므로 rows[0]이 최신, rows[20]이 20일 전
        latest = float(rows[0])
        prior = float(rows[20])
        if prior == 0:
            return None
        return (latest - prior) / prior * 100
    except Exception as e:
        logger.warning(f"market_return_20d 조회 실패: {e}")
        return None
    finally:
        db.close()
