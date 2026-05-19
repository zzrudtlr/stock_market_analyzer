from sqlalchemy import Column, BigInteger, String, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Disclosure(Base):
    __tablename__ = "disclosures"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20))
    corp_code = Column(String(20))
    report_date = Column(Date, nullable=False)
    receipt_no = Column(String(50))
    title = Column(String(300), nullable=False)
    disclosure_type = Column(String(100))
    risk_level = Column(String(20))
    summary = Column(Text)
    url = Column(String(500))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
