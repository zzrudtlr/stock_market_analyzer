import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models.stock import Stock

logger = logging.getLogger(__name__)


def get_stocks(
    session: Optional[Session] = None,
    market: Optional[str] = None,
    is_active: int = 1,
    limit: int = 5000,
) -> list[dict]:
    own_session = session is None
    db = session or get_db_session()
    try:
        q = select(Stock)
        if market:
            q = q.where(Stock.market == market)
        if is_active is not None:
            q = q.where(Stock.is_active == is_active)
        q = q.limit(limit)
        rows = db.execute(q).scalars().all()
        return [
            {
                "id": r.id,
                "market": r.market,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "sector": r.sector,
                "industry": r.industry,
                "listing_date": str(r.listing_date) if r.listing_date else None,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    finally:
        if own_session:
            db.close()


def get_stock_by_code(stock_code: str, session: Optional[Session] = None) -> Optional[dict]:
    own_session = session is None
    db = session or get_db_session()
    try:
        row = db.execute(select(Stock).where(Stock.stock_code == stock_code)).scalar_one_or_none()
        if not row:
            return None
        return {
            "id": row.id,
            "market": row.market,
            "stock_code": row.stock_code,
            "stock_name": row.stock_name,
            "sector": row.sector,
            "industry": row.industry,
            "listing_date": str(row.listing_date) if row.listing_date else None,
            "is_active": row.is_active,
        }
    finally:
        if own_session:
            db.close()


def get_active_stock_codes(market: Optional[str] = None) -> list[str]:
    db = get_db_session()
    try:
        q = select(Stock.stock_code).where(Stock.is_active == 1)
        if market:
            q = q.where(Stock.market == market)
        return [row[0] for row in db.execute(q).all()]
    finally:
        db.close()
