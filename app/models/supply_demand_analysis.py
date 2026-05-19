from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class SupplyDemandAnalysis(Base):
    """수급 분석 결과 — supply_demand_analysis_results 테이블"""
    __tablename__ = "supply_demand_analysis_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_sda_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # 당일 순매수 (단위: 백만원, 양수=순매수, 음수=순매도)
    foreign_net_buy     = Column(Numeric(20, 2))  # 외국인 순매수
    institution_net_buy = Column(Numeric(20, 2))  # 기관 순매수
    individual_net_buy  = Column(Numeric(20, 2))  # 개인 순매수
    program_net_buy     = Column(Numeric(20, 2))  # 프로그램 순매수

    # 5일 누적 순매수
    foreign_net_buy_5d     = Column(Numeric(20, 2))
    institution_net_buy_5d = Column(Numeric(20, 2))

    # 연속 순매수/순매도 일수 (양수=연속순매수, 음수=연속순매도)
    foreign_buy_streak     = Column(Integer, default=0)
    institution_buy_streak = Column(Integer, default=0)

    # 공매도
    short_sell_ratio  = Column(Numeric(8, 4))   # 공매도 비중 (%)
    short_sell_volume = Column(BigInteger)       # 공매도 수량 (주)

    # 수급 종합 신호 및 점수
    supply_signal = Column(String(30))           # 쌍끌기매수 / 외국인주도 / 기관주도 / 혼조 / 매도우위 등
    supply_score  = Column(Numeric(8, 4))        # -100 ~ +100

    # AI 해설
    ai_supply_summary = Column(Text)   # 수급 현황 요약
    ai_supply_flow    = Column(Text)   # 자금 흐름 특징
    ai_supply_risk    = Column(Text)   # 주의사항·리스크

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
