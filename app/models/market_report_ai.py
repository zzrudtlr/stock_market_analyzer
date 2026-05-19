from sqlalchemy import Column, BigInteger, String, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class MarketReportAI(Base):
    __tablename__ = "market_report_ai"

    id                      = Column(BigInteger, primary_key=True, autoincrement=True)
    report_date             = Column(Date, nullable=False)
    market_ai_summary       = Column(Text)
    bullish_market_comment  = Column(Text)
    bearish_market_comment  = Column(Text)
    risk_market_comment     = Column(Text)
    volume_market_comment   = Column(Text)
    created_at              = Column(DateTime, nullable=False, server_default=func.now())
    updated_at              = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
