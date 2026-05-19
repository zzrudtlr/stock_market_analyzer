from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class ThemeRotationResult(Base):
    """테마 순환 분석 결과 (테마별) — theme_rotation_results 테이블"""
    __tablename__ = "theme_rotation_results"
    __table_args__ = (
        UniqueConstraint("analysis_date", "theme_name", name="uq_trr_date_name"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date = Column(Date, nullable=False, index=True)
    theme_name    = Column(String(100), nullable=False)
    stock_count   = Column(Integer, default=0)   # 유효 데이터 종목 수

    # ── 오전 지표 (갭: 전일 종가 → 당일 시가) ──────────────────────
    theme_morning_score = Column(Numeric(8, 4))  # 평균 갭률 (%)

    # ── 장중 지표 (오후: 시가 → 종가 등락) ─────────────────────────
    theme_intraday_score = Column(Numeric(8, 4))  # 평균 시가 대비 종가 변화율 (%)

    # ── 장마감 지표 (종가 위치: 당일 범위 내 [0, 1]) ───────────────
    theme_close_strength = Column(Numeric(6, 4))  # avg (close-low)/(high-low)

    # ── 순환 점수 ──────────────────────────────────────────────────
    theme_rotation_score = Column(Numeric(6, 2))  # -100 ~ +100
    theme_flow_strength  = Column(Numeric(6, 2))  # 0 ~ 100 (자금 흐름 강도)
    intraday_theme_rank  = Column(Integer)          # 당일 장중 강세 순위 (1=최강)

    # ── 순환 시그널 ────────────────────────────────────────────────
    rotation_signal = Column(String(20))
    # 순환매 유입 / 유지 강세 / 횡보 / 이탈 / 약세 지속

    # ── 전일 대비 순위 변화 ────────────────────────────────────────
    prev_intraday_rank = Column(Integer)   # 전일 intraday_theme_rank
    rank_change        = Column(Integer)   # 순위 상승(양수) / 하락(음수)

    # ── 거래대금 집계 ──────────────────────────────────────────────
    total_trading_value = Column(BigInteger)   # 테마 종목 합산 거래대금 (원)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ThemeRotationSummary(Base):
    """테마 순환 일별 요약 — theme_rotation_summary 테이블"""
    __tablename__ = "theme_rotation_summary"
    __table_args__ = (
        UniqueConstraint("analysis_date", name="uq_trs_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date = Column(Date, nullable=False, index=True)

    total_themes_analyzed = Column(Integer, default=0)

    # 각 시간대별 강세 테마 (JSON list)
    top_morning_themes  = Column(Text)   # 오전 갭 상위
    top_intraday_themes = Column(Text)   # 장중(오후) 강세 상위
    top_close_themes    = Column(Text)   # 장마감 강세 상위

    # 순환 테마 (JSON list)
    rotation_inflow  = Column(Text)   # 순환매 유입 테마
    rotation_outflow = Column(Text)   # 이탈 테마

    # 순환매 체인 (텍스트: "AI → 반도체 → 전력" 형태)
    rotation_chain = Column(Text)

    # AI 해설
    ai_rotation_overview  = Column(Text)   # 전체 순환 흐름 종합
    ai_theme_flow_comment = Column(Text)   # 테마 자금 흐름 특징

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
