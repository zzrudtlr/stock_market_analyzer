from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from app.database import Base


class ThemeAnalysisResult(Base):
    """테마 분석 결과 (확장 버전) — theme_analysis_results 테이블"""
    __tablename__ = "theme_analysis_results"
    __table_args__ = (
        UniqueConstraint("analysis_date", "theme_name", name="uq_tar_date_name"),
    )

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date  = Column(Date, nullable=False, index=True)
    theme_name     = Column(String(100), nullable=False)

    # 6단계 시그널: 매우 강세 / 강세 흐름 / 순환매 관심 / 혼조 / 약세 흐름 / 하락 주의
    theme_signal   = Column(String(20))

    # 수익률 지표
    avg_return_1d  = Column(Numeric(8, 4))
    avg_return_5d  = Column(Numeric(8, 4))
    avg_return_20d = Column(Numeric(8, 4))

    # 거래량·비율
    avg_volume_ratio = Column(Numeric(10, 4))

    # 강세/약세 비율 (%)
    bullish_ratio  = Column(Numeric(5, 2))
    bearish_ratio  = Column(Numeric(5, 2))

    # 점수 평균
    momentum_avg   = Column(Numeric(8, 4))
    trend_avg      = Column(Numeric(8, 4))
    risk_avg       = Column(Numeric(8, 4))

    # 종목 수
    stock_count    = Column(Integer, default=0)
    stock_codes    = Column(Text)   # JSON list

    # 스포트라이트 종목 (JSON 문자열)
    strongest_stock     = Column(Text)   # {code, name, return_5d}
    weakest_stock       = Column(Text)   # {code, name, return_5d}
    volume_leader       = Column(Text)   # {code, name, volume_ratio}
    momentum_leader     = Column(Text)   # {code, name, momentum_score}
    risk_warning_stock  = Column(Text)   # {code, name, risk_score}

    # AI 해설 (5개 필드)
    ai_theme_summary           = Column(Text)  # 테마 현황 요약 1~2문장
    ai_theme_risk              = Column(Text)  # 리스크 및 주의사항
    ai_theme_flow              = Column(Text)  # 자금 흐름 및 수급 특징
    ai_theme_volume_comment    = Column(Text)  # 거래량 특이 사항
    ai_theme_rotation_comment  = Column(Text)  # 순환매 가능성

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
