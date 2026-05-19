from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class ThemeAnalysis(Base):
    __tablename__ = "theme_analysis"
    __table_args__ = (
        UniqueConstraint("report_date", "theme_name", name="uq_theme_date_name"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    report_date   = Column(Date, nullable=False, index=True)
    theme_name    = Column(String(100), nullable=False)

    stock_codes   = Column(Text)          # JSON list ["005930", ...]
    stock_count   = Column(Integer, default=0)

    avg_return_1d    = Column(Numeric(8, 4))
    avg_return_5d    = Column(Numeric(8, 4))
    avg_return_20d   = Column(Numeric(8, 4))
    avg_bullish_score = Column(Numeric(8, 4))
    avg_bearish_score = Column(Numeric(8, 4))
    bullish_count    = Column(Integer, default=0)
    bearish_count    = Column(Integer, default=0)

    theme_signal  = Column(String(20))    # 강세 / 약세 / 중립

    ai_summary    = Column(Text)
    ai_reason     = Column(Text)
    ai_outlook    = Column(Text)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
