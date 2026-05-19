from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class NewsSentimentResult(Base):
    """뉴스 감성 분석 결과 — news_sentiment_results 테이블"""
    __tablename__ = "news_sentiment_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_nsr_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # 수집 통계
    total_news_count    = Column(Integer, default=0)   # 전체 뉴스 수
    positive_news_count = Column(Integer, default=0)   # 호재
    negative_news_count = Column(Integer, default=0)   # 악재
    neutral_news_count  = Column(Integer, default=0)   # 중립

    # 소스별 카운트
    google_news_count = Column(Integer, default=0)
    naver_news_count  = Column(Integer, default=0)
    dart_news_count   = Column(Integer, default=0)

    # 감성 점수 및 시그널
    news_sentiment_score  = Column(Numeric(8, 4))  # -100 ~ +100
    news_sentiment_signal = Column(String(20))      # 강한 호재 / 호재 우세 / 중립 / 악재 우세 / 강한 악재

    # 수집된 헤드라인 (JSON: [{title, source, sentiment, reason}, ...])
    headlines_json = Column(Text)

    # AI 해설 (3개 필드)
    ai_sentiment_summary = Column(Text)  # 전반적 감성 요약
    ai_key_issues        = Column(Text)  # 주요 이슈 요약
    ai_sentiment_risk    = Column(Text)  # 뉴스 기반 리스크

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
