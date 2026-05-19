from sqlalchemy import BigInteger, Column, Date, DateTime, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class FundamentalAnalysisResult(Base):
    """기업 펀더멘털 분석 결과 — fundamental_analysis_results 테이블"""
    __tablename__ = "fundamental_analysis_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_fundament_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # 연간 매출액 (억원), 최신→과거 순
    revenue_current = Column(BigInteger)
    revenue_prev1   = Column(BigInteger)
    revenue_prev2   = Column(BigInteger)

    # 연간 영업이익 (억원)
    op_income_current = Column(BigInteger)
    op_income_prev1   = Column(BigInteger)
    op_income_prev2   = Column(BigInteger)

    # 연간 당기순이익 (억원)
    net_income_current = Column(BigInteger)
    net_income_prev1   = Column(BigInteger)
    net_income_prev2   = Column(BigInteger)

    # 성장률 (%)
    revenue_growth          = Column(Numeric(8, 2))
    operating_income_growth = Column(Numeric(8, 2))
    net_income_growth       = Column(Numeric(8, 2))
    eps_growth              = Column(Numeric(8, 2))

    # 밸류에이션 지표
    eps        = Column(BigInteger)      # 주당순이익 (원)
    per        = Column(Numeric(8, 2))   # 주가수익비율 (배)
    pbr        = Column(Numeric(8, 2))   # 주가순자산비율 (배)
    roe        = Column(Numeric(8, 2))   # 자기자본이익률 (%)
    debt_ratio = Column(Numeric(8, 2))   # 부채비율 (%)

    # 분석 점수 (-100 ~ +100)
    roe_score         = Column(Numeric(6, 2))
    debt_risk_score   = Column(Numeric(6, 2))
    valuation_score   = Column(Numeric(6, 2))
    fundamental_score = Column(Numeric(6, 2))

    # 시그널
    fundamental_signal = Column(String(20))   # 매우 우량 / 우량 / 보통 / 주의 / 위험

    # AI 해설
    ai_fundamental_summary = Column(Text)
    ai_growth_comment      = Column(Text)
    ai_valuation_comment   = Column(Text)
    ai_risk_comment        = Column(Text)

    data_source = Column(String(50), default="naver")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
