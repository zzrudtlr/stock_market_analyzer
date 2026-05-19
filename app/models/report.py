from sqlalchemy import Column, BigInteger, String, Date, Text, JSON, DateTime
from sqlalchemy.sql import func
from app.database import Base


class DailyMarketReport(Base):
    __tablename__ = "daily_market_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False)
    title = Column(String(200), nullable=False)
    market_summary = Column(Text)
    bullish_summary = Column(Text)
    bearish_summary = Column(Text)
    disclosure_summary = Column(Text)
    markdown_content = Column(Text)
    html_content = Column(Text)
    json_content = Column(JSON)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
