from sqlalchemy import Column, BigInteger, String, Date, Numeric, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class StockAnalysisResult(Base):
    __tablename__ = "stock_analysis_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    analysis_date = Column(Date, nullable=False)
    daily_return = Column(Numeric(8, 4))
    return_5d = Column(Numeric(8, 4))
    return_20d = Column(Numeric(8, 4))
    return_60d = Column(Numeric(8, 4))
    volume_ratio_5d = Column(Numeric(10, 4))
    volume_ratio_20d = Column(Numeric(10, 4))
    ma5 = Column(Numeric(18, 4))
    ma20 = Column(Numeric(18, 4))
    ma60 = Column(Numeric(18, 4))
    ma120 = Column(Numeric(18, 4))
    rsi14 = Column(Numeric(8, 4))
    volatility_20d = Column(Numeric(8, 4))
    relative_strength = Column(Numeric(8, 4))
    momentum_score = Column(Numeric(8, 4))
    volume_score = Column(Numeric(8, 4))
    trend_score = Column(Numeric(8, 4))
    risk_score = Column(Numeric(8, 4))
    disclosure_score = Column(Numeric(8, 4))
    bullish_score = Column(Numeric(8, 4))
    bearish_score = Column(Numeric(8, 4))
    final_signal = Column(String(50))
    signal_reason = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
