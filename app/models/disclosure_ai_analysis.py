from sqlalchemy import Column, BigInteger, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DisclosureAIAnalysis(Base):
    __tablename__ = "disclosure_ai_analysis"

    id                    = Column(BigInteger, primary_key=True, autoincrement=True)
    disclosure_id         = Column(BigInteger, nullable=False)   # disclosures.id
    stock_code            = Column(String(20), nullable=False)
    ai_disclosure_summary = Column(Text)
    ai_disclosure_risk    = Column(String(20))                   # 낮음/보통/높음/주의
    ai_market_impact      = Column(Text)
    created_at            = Column(DateTime, nullable=False, server_default=func.now())
    updated_at            = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
