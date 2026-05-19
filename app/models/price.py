from sqlalchemy import Column, BigInteger, String, Date, Numeric, DateTime
from sqlalchemy.sql import func
from app.database import Base


class StockDailyPrice(Base):
    __tablename__ = "stock_daily_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    open_price = Column(BigInteger)
    high_price = Column(BigInteger)
    low_price = Column(BigInteger)
    close_price = Column(BigInteger)
    change_price = Column(BigInteger)
    change_rate = Column(Numeric(8, 4))
    volume = Column(BigInteger)
    trading_value = Column(BigInteger)
    market_cap = Column(BigInteger)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
