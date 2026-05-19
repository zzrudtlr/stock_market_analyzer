from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class MarketLeaderResult(Base):
    """시장 주도주 분석 결과 (종목별) — market_leader_results 테이블"""
    __tablename__ = "market_leader_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_mlr_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # 종목 기본 정보 (비정규화)
    stock_name = Column(String(100))
    market     = Column(String(20))    # KOSPI / KOSDAQ
    sector     = Column(String(100))

    # 거래대금
    trading_value         = Column(BigInteger)         # 당일 거래대금 (원)
    trading_value_rank    = Column(Integer)            # 거래대금 순위 (1=최고)
    trading_value_vs_avg5 = Column(Numeric(10, 2))    # 5일 평균 대비 변화율 (%)

    # 시가총액
    market_cap       = Column(BigInteger)              # 시가총액 (원)
    market_cap_rank  = Column(Integer)                 # 시가총액 순위

    # 점수 항목 (0~100)
    market_influence_score   = Column(Numeric(6, 2))  # 시가총액 영향력
    relative_strength        = Column(Numeric(8, 4))  # 상대강도 원값 (1.0 기준)
    relative_strength_score  = Column(Numeric(6, 2))  # 상대강도 점수
    volume_ratio_20d         = Column(Numeric(10, 4)) # 20일 평균 대비 거래량 비율
    volume_score             = Column(Numeric(6, 2))  # 거래량 점수

    # 테마
    theme_name            = Column(String(100))
    theme_signal          = Column(String(20))
    theme_influence_score = Column(Numeric(6, 2))     # 테마 영향력 점수

    # 종합
    market_leader_score = Column(Numeric(6, 2))       # 시장 주도 종합 점수 (0~100)
    leader_signal       = Column(String(20))           # 시장 주도주 / 주도 후보 / 관심 종목 / 일반

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class MarketLeaderSummary(Base):
    """시장 주도주 일별 요약 — market_leader_summary 테이블"""
    __tablename__ = "market_leader_summary"
    __table_args__ = (
        UniqueConstraint("analysis_date", name="uq_mls_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date = Column(Date, nullable=False, index=True)

    total_analyzed    = Column(Integer, default=0)
    leader_count      = Column(Integer, default=0)   # leader_signal = 시장 주도주 수
    kospi_leader_count  = Column(Integer, default=0)
    kosdaq_leader_count = Column(Integer, default=0)

    # Top 리스트 (JSON 문자열)
    top_leaders          = Column(Text)   # 시장 주도 점수 상위 10
    top_trading_value    = Column(Text)   # 거래대금 상위 10
    top_market_influence = Column(Text)   # 시총 영향력 상위 5
    dominant_themes      = Column(Text)   # 주도 테마 목록 (JSON list)

    # AI 해설
    ai_market_summary  = Column(Text)   # 시장 주도 흐름 종합
    ai_theme_flow      = Column(Text)   # 테마 집중 현상
    ai_leader_comment  = Column(Text)   # 주도주 특징 해설

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
