from sqlalchemy import Column, BigInteger, String, Date, Numeric, DateTime
from sqlalchemy.sql import func
from app.database import Base


class MarketIndex(Base):
    __tablename__ = "market_indices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    index_code = Column(String(30), nullable=False)
    index_name = Column(String(100), nullable=False)
    trade_date = Column(Date, nullable=False)
    close_value = Column(Numeric(12, 4))
    change_value = Column(Numeric(12, 4))
    change_rate = Column(Numeric(8, 4))
    volume = Column(BigInteger)
    trading_value = Column(BigInteger)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
