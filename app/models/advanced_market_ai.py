from sqlalchemy import BigInteger, Column, Date, DateTime, String, Text, UniqueConstraint, func

from app.database import Base


class AdvancedMarketAI(Base):
    """종합 시장 AI 해설 — advanced_market_ai 테이블"""
    __tablename__ = "advanced_market_ai"
    __table_args__ = (
        UniqueConstraint("report_date", name="uq_ama_date"),
    )

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False, index=True)

    # ── AI 출력 (5개 해설 필드) ────────────────────────────────────
    ai_market_flow_summary   = Column(Text)  # 전체 시장 흐름 (지수+강약세+자금 방향)
    ai_stock_summary         = Column(Text)  # 주요 종목 흐름 (주도주+차트+수급 연계)
    ai_risk_summary          = Column(Text)  # 위험 요인 종합 (과열+공시+뉴스 악재)
    ai_theme_summary         = Column(Text)  # 테마 순환 흐름 (순환매+주도+이탈)
    ai_supply_demand_summary = Column(Text)  # 수급 흐름 (외국인/기관+공매도+테마)

    # 입력 데이터 요약 (JSON — 투명성 확보, 디버깅용)
    data_context = Column(Text)
    model_used   = Column(String(30), default="gpt-4o-mini")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
