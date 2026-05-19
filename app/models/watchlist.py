from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class WatchlistGroup(Base):
    __tablename__ = "watchlist_groups"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_name = Column(String(100), nullable=False)
    description = Column(String(300))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, nullable=False)
    stock_code = Column(String(20), nullable=False)
    memo = Column(String(500))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
