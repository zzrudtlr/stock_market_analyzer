from sqlalchemy import Column, BigInteger, String, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class StockAIAnalysis(Base):
    __tablename__ = "stock_ai_analysis"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False)
    analysis_date = Column(Date, nullable=False)
    ai_summary         = Column(Text)
    ai_trend_comment   = Column(Text)
    ai_risk_comment    = Column(Text)
    ai_volume_comment  = Column(Text)
    ai_signal_comment  = Column(Text)
    created_at    = Column(DateTime, nullable=False, server_default=func.now())
    updated_at    = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
