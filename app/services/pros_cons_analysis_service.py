"""
긍정 요소 / 위험 요소 분리 표시 기능
초보자가 좋은 점과 위험 요소를 동시에 이해할 수 있도록 구성
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ProConType(Enum):
    """긍정/위험 요소 유형"""
    VOLUME = "volume"  # 거래량
    TREND = "trend"  # 추세
    SUPPLY = "supply"  # 수급
    THEME = "theme"  # 테마
    SENTIMENT = "sentiment"  # 뉴스 심리
    VOLATILITY = "volatility"  # 변동성
    FUNDAMENTAL = "fundamental"  # 실적
    TECHNICAL = "technical"  # 기술
    

@dataclass
class ProConPoint:
    """긍정/위험 포인트"""
    factor: str  # 요인 (예: "거래량 증가")
    factor_type: ProConType  # 요인 유형
    description: str  # 설명
    impact_level: str  # 영향도 (high, medium, low)
    beginner_comment: str  # 초보자용 설명
    emoji: str = ""  # 이모지
    
    def to_dict(self):
        data = asdict(self)
        data['factor_type'] = self.factor_type.value
        return data


class ProsConsAnalysisService:
    """긍정/위험 요소 분리 분석 서비스"""
    
    # 긍정 요소 정의
    POSITIVE_FACTORS = {
        "volume_increase": ProConPoint(
            factor="거래량 증가",
            factor_type=ProConType.VOLUME,
            description="일일 거래량이 평소 대비 크게 증가",
            impact_level="high",
            beginner_comment="많은 투자자가 이 종목에 관심을 가지고 있습니다. 시장 관심도가 높아지고 있는 상태입니다.",
            emoji="📈"
        ),
        "foreign_buying": ProConPoint(
            factor="외국인 순매수",
            factor_type=ProConType.SUPPLY,
            description="외국인 투자자의 지속적인 순매수",
            impact_level="high",
            beginner_comment="해외 투자자들이 매수하고 있습니다. 글로벌 시장에서도 관심을 받는 신호일 수 있습니다.",
            emoji="🌍"
        ),
        "institution_buying": ProConPoint(
            factor="기관 순매수",
            factor_type=ProConType.SUPPLY,
            description="국내 기관투자자의 순매수",
            impact_level="high",
            beginner_comment="국내 펀드와 보험사 같은 기관들이 매수하고 있습니다. 전문가들의 긍정적 판단으로 볼 수 있습니다.",
            emoji="🏢"
        ),
        "uptrend_formation": ProConPoint(
            factor="상승 추세 형성",
            factor_type=ProConType.TREND,
            description="단기/중기/장기 이동평균이 모두 상승",
            impact_level="high",
            beginner_comment="단기부터 장기까지 모두 상승 흐름입니다. 다양한 기간에서 긍정적인 신호가 보입니다.",
            emoji="📊"
        ),
        "ma_crossover": ProConPoint(
            factor="골든크로스 형성",
            factor_type=ProConType.TECHNICAL,
            description="단기 이동평균이 장기 이동평균을 뚫고 올라감",
            impact_level="medium",
            beginner_comment="차트 기술 분석에서 주목받는 상승 신호입니다. 다만, 항상 상승을 의미하지는 않습니다.",
            emoji="✨"
        ),
        "positive_news": ProConPoint(
            factor="긍정적 뉴스",
            factor_type=ProConType.SENTIMENT,
            description="좋은 뉴스와 긍정적 시장 평가",
            impact_level="medium",
            beginner_comment="최근 종목과 관련된 긍정적인 뉴스가 나오고 있습니다. 투자자들의 기대감이 높아지는 중입니다.",
            emoji="📰"
        ),
        "strong_theme": ProConPoint(
            factor="강한 테마 흐름",
            factor_type=ProConType.THEME,
            description="속한 업종/테마가 시장에서 강세",
            impact_level="medium",
            beginner_comment="이 종목이 속한 테마나 업종이 시장에서 주목받고 있습니다. 테마 강세의 수혜를 보고 있습니다.",
            emoji="🎯"
        ),
        "strong_rsi": ProConPoint(
            factor="강한 단기 흐름",
            factor_type=ProConType.TECHNICAL,
            description="RSI 지표가 50~70 사이의 양호한 수준",
            impact_level="medium",
            beginner_comment="단기 상승 강도가 건강한 수준입니다. 강하지만 과열되지 않은 상태입니다.",
            emoji="⚡"
        ),
        "price_recovery": ProConPoint(
            factor="가격 회복",
            factor_type=ProConType.TREND,
            description="저점에서 회복세를 보임",
            impact_level="medium",
            beginner_comment="저점에서 올라오는 회복 흐름을 보이고 있습니다. 매수세가 들어오는 신호일 수 있습니다.",
            emoji="🔄"
        ),
    }
    
    # 위험 요소 정의
    RISK_FACTORS = {
        "overbought": ProConPoint(
            factor="단기 과열",
            factor_type=ProConType.TECHNICAL,
            description="RSI > 75로 단기 과열 상태",
            impact_level="high",
            beginner_comment="주가가 단기적으로 과도하게 올라있는 상태입니다. 급락 가능성에 주의가 필요합니다.",
            emoji="🔥"
        ),
        "oversold": ProConPoint(
            factor="단기 과도 하락",
            factor_type=ProConType.TECHNICAL,
            description="RSI < 25로 단기 과도 하락",
            impact_level="high",
            beginner_comment="주가가 단기적으로 과도하게 내려있는 상태입니다. 급등 가능성도 있지만 위험성도 있습니다.",
            emoji="📉"
        ),
        "high_volatility": ProConPoint(
            factor="높은 변동성",
            factor_type=ProConType.VOLATILITY,
            description="주가 변동폭이 비정상적으로 큼",
            impact_level="high",
            beginner_comment="주가가 크게 오르내리는 상태입니다. 큰 수익 기회도 있지만 손실 위험도 큽니다.",
            emoji="⚠️"
        ),
        "foreign_selling": ProConPoint(
            factor="외국인 순매도",
            factor_type=ProConType.SUPPLY,
            description="외국인 투자자의 지속적인 순매도",
            impact_level="high",
            beginner_comment="해외 투자자들이 팔고 있습니다. 글로벌 자금 유출 신호일 수 있습니다.",
            emoji="🌍📉"
        ),
        "negative_news": ProConPoint(
            factor="부정적 뉴스",
            factor_type=ProConType.SENTIMENT,
            description="나쁜 뉴스와 부정적인 시장 평가",
            impact_level="high",
            beginner_comment="종목과 관련된 부정적인 뉴스가 있습니다. 시장의 우려감이 높아지는 중입니다.",
            emoji="📰⚠️"
        ),
        "downtrend_formation": ProConPoint(
            factor="하락 추세 형성",
            factor_type=ProConType.TREND,
            description="이동평균선이 모두 하향",
            impact_level="high",
            beginner_comment="단기부터 장기까지 하락 추세가 형성되어 있습니다. 추세를 거스르기 어려운 상태입니다.",
            emoji="📊📉"
        ),
        "dead_cross": ProConPoint(
            factor="데드크로스 형성",
            factor_type=ProConType.TECHNICAL,
            description="단기 이동평균이 장기 이동평균을 뚫고 내려감",
            impact_level="high",
            beginner_comment="차트 기술 분석에서 하락 신호로 보는 패턴입니다. 추가 하락 가능성에 주의가 필요합니다.",
            emoji="⛔"
        ),
        "weak_theme": ProConPoint(
            factor="약해진 테마",
            factor_type=ProConType.THEME,
            description="속한 업종/테마가 약세 중",
            impact_level="medium",
            beginner_comment="이 종목이 속한 테마가 시장에서 외면받고 있습니다. 테마 약세의 영향을 받을 수 있습니다.",
            emoji="❌"
        ),
        "large_short_selling": ProConPoint(
            factor="대규모 공매도",
            factor_type=ProConType.SUPPLY,
            description="공매도 잔량이 많거나 급증",
            impact_level="medium",
            beginner_comment="공매도자들이 많은 주식을 빌려 팔고 있습니다. 가격 하락을 예상하는 세력이 있다는 신호입니다.",
            emoji="📊⬇️"
        ),
        "price_collapse": ProConPoint(
            factor="급격한 하락",
            factor_type=ProConType.TREND,
            description="단시간에 가격이 크게 하락",
            impact_level="high",
            beginner_comment="최근 급락이 있었습니다. 원인을 파악하고 추가 하락 가능성을 확인해야 합니다.",
            emoji="💥📉"
        ),
    }
    
    @classmethod
    def analyze_pros_and_cons(cls, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        분석 데이터를 기반으로 긍정/위험 요소 추출
        
        Args:
            analysis_data: 분석 데이터
            
        Returns:
            긍정 요소, 위험 요소, 종합 평가를 포함한 딕셔너리
        """
        positive_points: List[ProConPoint] = []
        risk_points: List[ProConPoint] = []
        
        # 거래량 분석
        volume_change_rate = analysis_data.get("volume_change_rate", 0)
        if volume_change_rate > 100:
            positive_points.append(cls.POSITIVE_FACTORS["volume_increase"])
        
        # 수급 분석
        foreign_net = analysis_data.get("foreign_net", 0)
        if foreign_net > 0:
            positive_points.append(cls.POSITIVE_FACTORS["foreign_buying"])
        elif foreign_net < 0:
            risk_points.append(cls.RISK_FACTORS["foreign_selling"])
        
        institution_net = analysis_data.get("institution_net", 0)
        if institution_net > 0:
            positive_points.append(cls.POSITIVE_FACTORS["institution_buying"])
        
        # 기술 분석
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        rsi = analysis_data.get("rsi", 50)
        
        # 추세 분석
        if current_price > 0 and ma5 > 0 and ma20 > 0 and ma60 > 0:
            if current_price > ma5 > ma20 > ma60:
                positive_points.append(cls.POSITIVE_FACTORS["uptrend_formation"])
            elif ma5 > ma20 > ma60:
                positive_points.append(cls.POSITIVE_FACTORS["ma_crossover"])
            
            if current_price < ma5 < ma20 < ma60:
                risk_points.append(cls.RISK_FACTORS["downtrend_formation"])
            elif ma5 < ma20 < ma60:
                risk_points.append(cls.RISK_FACTORS["dead_cross"])
        
        # RSI 분석
        if rsi > 75:
            risk_points.append(cls.RISK_FACTORS["overbought"])
        elif rsi < 25:
            risk_points.append(cls.RISK_FACTORS["oversold"])
        elif rsi > 60:
            positive_points.append(cls.POSITIVE_FACTORS["strong_rsi"])
        
        # 변동성 분석
        volatility_level = analysis_data.get("volatility_level", "normal")
        if volatility_level == "high":
            risk_points.append(cls.RISK_FACTORS["high_volatility"])
        
        # 뉴스 감정 분석
        news_sentiment = analysis_data.get("news_sentiment", "neutral")
        if news_sentiment == "positive":
            positive_points.append(cls.POSITIVE_FACTORS["positive_news"])
        elif news_sentiment == "negative":
            risk_points.append(cls.RISK_FACTORS["negative_news"])
        
        # 테마 분석
        theme_strength = analysis_data.get("theme_strength", "weak")
        if theme_strength == "strong":
            positive_points.append(cls.POSITIVE_FACTORS["strong_theme"])
        elif theme_strength == "weak":
            risk_points.append(cls.RISK_FACTORS["weak_theme"])
        
        # 공매도 분석
        short_selling = analysis_data.get("short_selling", 0)
        if short_selling > 100000:  # 100만 주 이상
            risk_points.append(cls.RISK_FACTORS["large_short_selling"])
        
        # 결과 컴파일
        result = {
            "positive_points": [p.to_dict() for p in positive_points],
            "risk_points": [p.to_dict() for p in risk_points],
            "positive_count": len(positive_points),
            "risk_count": len(risk_points),
            "overall_assessment": cls._generate_overall_assessment(
                positive_points, risk_points, analysis_data
            ),
            "recommendation_level": cls._calculate_recommendation_level(
                positive_points, risk_points
            )
        }
        
        return result
    
    @staticmethod
    def _generate_overall_assessment(
        positive_points: List[ProConPoint],
        risk_points: List[ProConPoint],
        analysis_data: Dict[str, Any]
    ) -> str:
        """
        긍정/위험 요소를 종합하여 초보자 친화형 평가 생성
        
        Args:
            positive_points: 긍정 포인트 리스트
            risk_points: 위험 포인트 리스트
            analysis_data: 분석 데이터
            
        Returns:
            종합 평가 문구
        """
        assessment = ""
        
        # 요소 수 기반 평가
        if len(positive_points) > len(risk_points):
            assessment = "현재 긍정적인 신호들이 더 많이 보입니다. "
        elif len(positive_points) < len(risk_points):
            assessment = "현재 위험 신호들이 더 많이 보입니다. "
        else:
            assessment = "현재 긍정 신호와 위험 신호가 섞여 있습니다. "
        
        # 상세 내용 추가
        if positive_points:
            positive_types = set(p.factor_type.value for p in positive_points)
            assessment += f"특히 {', '.join(positive_types)} 측면에서 긍정 신호가 있습니다. "
        
        if risk_points:
            assessment += "다만, 위험 요소도 함께 고려해야 합니다. "
        
        assessment += "이는 참고용 분석이며, 투자 결정은 신중하게 하시기 바랍니다."
        
        return assessment
    
    @staticmethod
    def _calculate_recommendation_level(
        positive_points: List[ProConPoint],
        risk_points: List[ProConPoint]
    ) -> str:
        """
        추천 수준 계산
        
        Args:
            positive_points: 긍정 포인트
            risk_points: 위험 포인트
            
        Returns:
            추천 수준 (높음, 중간, 낮음, 주의)
        """
        positive_score = sum(
            3 if p.impact_level == "high" else 2 if p.impact_level == "medium" else 1
            for p in positive_points
        )
        
        risk_score = sum(
            3 if p.impact_level == "high" else 2 if p.impact_level == "medium" else 1
            for p in risk_points
        )
        
        diff = positive_score - risk_score
        
        if diff > 5:
            return "긍정적 신호 우위"
        elif diff > 2:
            return "약간의 긍정 신호"
        elif diff < -5:
            return "주의 필요"
        elif diff < -2:
            return "위험 신호 주의"
        else:
            return "중립"
    
    @classmethod
    def get_positive_points_summary(cls, positive_points: List[Dict]) -> str:
        """
        긍정 요소 요약 생성
        
        Args:
            positive_points: 긍정 포인트 리스트
            
        Returns:
            요약 문구
        """
        if not positive_points:
            return "특별한 긍정 신호는 보이지 않습니다."
        
        factors = [p["factor"] for p in positive_points[:3]]  # 상위 3개
        return f"긍정 요소: {', '.join(factors)}가 함께 보이고 있습니다."
    
    @classmethod
    def get_risk_points_summary(cls, risk_points: List[Dict]) -> str:
        """
        위험 요소 요약 생성
        
        Args:
            risk_points: 위험 포인트 리스트
            
        Returns:
            요약 문구
        """
        if not risk_points:
            return "특별한 위험 신호는 보이지 않습니다."
        
        factors = [p["factor"] for p in risk_points[:3]]  # 상위 3개
        return f"위험 요소: {', '.join(factors)}를 주의깊게 봐야 합니다."


# 싱글톤 인스턴스
pros_cons_analyzer = ProsConsAnalysisService()
