from sqlalchemy import BigInteger, Column, Date, DateTime, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class RiskAnalysisResult(Base):
    """종목 위험도 분석 결과 — risk_analysis_results 테이블"""
    __tablename__ = "risk_analysis_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_rar_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # ── 위험 세부 점수 (0 ~ 100, 높을수록 위험) ──────────────────────
    volatility_risk   = Column(Numeric(6, 2))   # 변동성 위험
    overheating_risk  = Column(Numeric(6, 2))   # 급등·거래량 과열
    disclosure_risk   = Column(Numeric(6, 2))   # 공시 위험
    sentiment_risk    = Column(Numeric(6, 2))   # 뉴스 악재
    financial_risk    = Column(Numeric(6, 2))   # 실적 악화
    supply_risk       = Column(Numeric(6, 2))   # 수급 불균형

    # ── 종합 ──────────────────────────────────────────────────────────
    total_risk_score = Column(Numeric(6, 2))    # 가중 평균 종합 위험 점수
    risk_grade       = Column(String(10))        # 안정 / 보통 / 주의 / 고위험 / 과열주의

    # 트리거된 위험 요인 목록 (JSON list of str)
    risk_factors = Column(Text)

    # ── AI 해설 ────────────────────────────────────────────────────────
    ai_risk_summary  = Column(Text)   # 위험 요인 종합 평가
    ai_risk_factors  = Column(Text)   # 주요 위험 요인 설명
    ai_risk_action   = Column(Text)   # 위험 관리 관점 제언

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
