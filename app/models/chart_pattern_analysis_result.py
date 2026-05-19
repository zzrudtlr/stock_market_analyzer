from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class ChartPatternAnalysisResult(Base):
    """차트 패턴 분석 결과 — chart_pattern_analysis_results 테이블"""
    __tablename__ = "chart_pattern_analysis_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "analysis_date", name="uq_chart_pattern_code_date"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code    = Column(String(20), nullable=False, index=True)
    analysis_date = Column(Date, nullable=False, index=True)

    # 패턴 탐지 시그널 (Boolean)
    breakout_signal        = Column(Boolean, default=False)   # 박스권 돌파
    new_high_signal        = Column(Boolean, default=False)   # 신고가 근접
    volume_breakout_signal = Column(Boolean, default=False)   # 거래량 동반 상승
    ma20_breakout_signal   = Column(Boolean, default=False)   # MA20 돌파
    ma60_breakout_signal   = Column(Boolean, default=False)   # MA60 돌파
    golden_cross_signal    = Column(Boolean, default=False)   # 골든크로스
    dead_cross_signal      = Column(Boolean, default=False)   # 데드크로스
    pullback_signal        = Column(Boolean, default=False)   # 눌림목 패턴

    # 이동평균 배열 상태
    ma_alignment = Column(String(10))    # 정배열 / 역배열 / 혼조 / 중립

    # 종합 점수 및 시그널
    pattern_score = Column(Numeric(6, 2))   # -100 ~ +100
    chart_signal  = Column(String(20))      # 강한상승패턴 / 상승패턴 / 중립 / 약세 / 하락주의

    # 현재가 대비 지표 (%)
    price_vs_ma20     = Column(Numeric(8, 2))   # MA20 대비 괴리율
    price_vs_ma60     = Column(Numeric(8, 2))   # MA60 대비 괴리율
    price_vs_52w_high = Column(Numeric(8, 2))   # 52주 고점 대비 괴리율
    volume_ratio_20d  = Column(Numeric(8, 2))   # 거래량 / 20일 평균 거래량

    # 탐지된 패턴 설명 (| 구분)
    pattern_descriptions = Column(Text)

    # AI 해설
    ai_chart_summary   = Column(Text)   # 차트 패턴 종합 평가
    ai_pattern_comment = Column(Text)   # 주요 패턴 설명
    ai_trend_comment   = Column(Text)   # 이동평균·추세 흐름

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
