from sqlalchemy import Column, BigInteger, String, Date, SmallInteger, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    market = Column(String(20), nullable=False)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    listing_date = Column(Date)
    is_active = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
