from sqlalchemy import Column, BigInteger, String, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class CollectorLog(Base):
    __tablename__ = "collector_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    collector_name = Column(String(100), nullable=False)
    target_date = Column(Date)
    status = Column(String(20), nullable=False)
    message = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
