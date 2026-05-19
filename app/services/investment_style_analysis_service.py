"""
투자 스타일 분류 기능
종목의 성향을 초보자가 쉽게 이해하도록 분류
"""

from typing import Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InvestmentStyle(Enum):
    """투자 스타일 유형"""
    SHORT_TERM_VOLATILE = "단기_변동형"
    TREND_STABLE = "추세_안정형"
    EARNINGS_GROWTH = "실적_성장형"
    THEME_CYCLICAL = "테마_순환형"
    HIGH_RISK_VOLATILE = "고위험_변동형"
    LOW_VOLATILITY_STABLE = "저변동_안정형"


@dataclass
class InvestmentStyleInfo:
    """투자 스타일 정보"""
    style: InvestmentStyle
    display_name: str
    description: str
    characteristics: list
    suitable_investor_type: str
    risk_level: str
    profit_potential: str
    key_points: list
    beginner_comment: str
    emoji: str


class InvestmentStyleAnalysisService:
    """투자 스타일 분석 서비스"""
    
    # 투자 스타일 정의
    STYLE_DEFINITIONS = {
        InvestmentStyle.SHORT_TERM_VOLATILE: InvestmentStyleInfo(
            style=InvestmentStyle.SHORT_TERM_VOLATILE,
            display_name="단기 변동형",
            description="단기 등락이 크고 변동성이 높은 종목",
            characteristics=[
                "거래량이 많음",
                "일일 변동폭이 큼",
                "추세가 자주 바뀜",
                "뉴스/테마 반응이 빠름"
            ],
            suitable_investor_type="단기 매매 경험자",
            risk_level="매우 높음",
            profit_potential="높음",
            key_points=[
                "급등과 급락 모두 가능",
                "단기 수익 기회 높음",
                "손실 위험도 높음",
                "꾸준한 모니터링 필요"
            ],
            beginner_comment="이 종목은 가격이 자주, 그리고 크게 움직입니다. 큰 수익을 기대할 수 있지만, 큰 손실도 가능합니다. 초보자에게는 어려울 수 있습니다.",
            emoji="📈📉"
        ),
        
        InvestmentStyle.TREND_STABLE: InvestmentStyleInfo(
            style=InvestmentStyle.TREND_STABLE,
            display_name="추세 안정형",
            description="명확한 추세를 보이며 상대적으로 안정적",
            characteristics=[
                "명확한 상승 또는 하락 추세",
                "일정한 패턴 유지",
                "변동성이 낮음",
                "추세 예측이 가능"
            ],
            suitable_investor_type="중기 투자자",
            risk_level="보통",
            profit_potential="보통~높음",
            key_points=[
                "추세 방향 파악이 중요",
                "추세 반전에 주의",
                "기술적 분석 활용 가능",
                "중기 투자에 적합"
            ],
            beginner_comment="이 종목은 일정한 추세(위 또는 아래)를 유지하고 있습니다. 추세를 따라가면 상대적으로 수익성이 높을 수 있습니다.",
            emoji="📊"
        ),
        
        InvestmentStyle.EARNINGS_GROWTH: InvestmentStyleInfo(
            style=InvestmentStyle.EARNINGS_GROWTH,
            display_name="실적 성장형",
            description="실적 개선에 따라 가격이 움직이는 종목",
            characteristics=[
                "실적이 개선 중",
                "기업 뉴스가 중요",
                "펀더멘탈 우수",
                "기관 투자자 관심"
            ],
            suitable_investor_type="장기 투자자",
            risk_level="낮음~보통",
            profit_potential="높음",
            key_points=[
                "실적 발표 시 변동성 증가",
                "장기 성장성 중요",
                "배당 가능성",
                "기업 상태 모니터링 필요"
            ],
            beginner_comment="이 종목은 회사의 실제 수익(실적)에 따라 가격이 움직입니다. 회사가 실적을 잘 내면 장기적으로 가격이 올라갈 가능성이 높습니다.",
            emoji="💹"
        ),
        
        InvestmentStyle.THEME_CYCLICAL: InvestmentStyleInfo(
            style=InvestmentStyle.THEME_CYCLICAL,
            display_name="테마 순환형",
            description="시장의 관심도에 따라 크게 영향을 받는 종목",
            characteristics=[
                "특정 테마에 포함됨",
                "테마 강세 시 급등",
                "테마 약세 시 급락",
                "뉴스 반응성 높음"
            ],
            suitable_investor_type="테마 트레이더",
            risk_level="높음",
            profit_potential="높음",
            key_points=[
                "테마 흐름 파악 필수",
                "테마 순환성 이해 필요",
                "시장 심리 중요",
                "타이밍이 매우 중요"
            ],
            beginner_comment="이 종목은 시장에서 '핫'한 이야기(테마)에 따라 가격이 크게 움직입니다. AI, 2차전지 같은 테마가 주목받으면 가격이 올라갑니다.",
            emoji="🎯"
        ),
        
        InvestmentStyle.HIGH_RISK_VOLATILE: InvestmentStyleInfo(
            style=InvestmentStyle.HIGH_RISK_VOLATILE,
            display_name="고위험 변동형",
            description="매우 높은 변동성과 위험성을 가진 종목",
            characteristics=[
                "극도의 변동성",
                "예측이 어려움",
                "급락/급등 가능",
                "소액주 또는 신생기업"
            ],
            suitable_investor_type="위험 감수 능력이 높은 투자자",
            risk_level="매우 높음",
            profit_potential="매우 높음",
            key_points=[
                "손실 가능성 매우 높음",
                "전체 자산의 일부만 투자 권장",
                "지속적 모니터링 필수",
                "손절/익절 계획 필수"
            ],
            beginner_comment="이 종목은 매우 위험합니다. 큰 수익을 얻을 수 있지만, 투자금 전부를 잃을 수도 있습니다. 초보자는 피하는 것이 좋습니다.",
            emoji="💥"
        ),
        
        InvestmentStyle.LOW_VOLATILITY_STABLE: InvestmentStyleInfo(
            style=InvestmentStyle.LOW_VOLATILITY_STABLE,
            display_name="저변동 안정형",
            description="변동성이 낮고 안정적인 종목",
            characteristics=[
                "변동성 낮음",
                "대형 우량주",
                "배당금 높음",
                "실적 안정적"
            ],
            suitable_investor_type="보수적 투자자",
            risk_level="낮음",
            profit_potential="낮음~보통",
            key_points=[
                "장기 보유 적합",
                "배당금 수익 가능",
                "큰 손실 위험 낮음",
                "기회도 적을 수 있음"
            ],
            beginner_comment="이 종목은 가격이 안정적으로 움직입니다. 큰 수익을 기대하기 어렵지만, 손실 위험도 적습니다. 초보자에게 적합할 수 있습니다.",
            emoji="🛡️"
        ),
    }
    
    @classmethod
    def analyze_investment_style(cls, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        분석 데이터를 기반으로 투자 스타일 판별
        
        Args:
            analysis_data: 분석 데이터
            
        Returns:
            투자 스타일 및 상세 정보
        """
        # 각 스타일에 대한 점수 계산
        scores = {style: 0 for style in InvestmentStyle}
        
        # 변동성 지표
        volatility_level = analysis_data.get("volatility_level", "normal")
        volume_change_rate = analysis_data.get("volume_change_rate", 0)
        rsi = analysis_data.get("rsi", 50)
        
        # 추세 지표
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        
        # 수급 지표
        foreign_net = analysis_data.get("foreign_net", 0)
        institution_net = analysis_data.get("institution_net", 0)
        
        # 실적 지표
        per = analysis_data.get("per", 0)
        roe = analysis_data.get("roe", 0)
        earnings_growth = analysis_data.get("earnings_growth", 0)
        
        # 테마/뉴스 지표
        theme_strength = analysis_data.get("theme_strength", "weak")
        news_sentiment = analysis_data.get("news_sentiment", "neutral")
        
        # 1. 고위험 변동형 판별
        if volatility_level == "high" and volume_change_rate > 200:
            scores[InvestmentStyle.HIGH_RISK_VOLATILE] += 5
        if rsi > 75 or rsi < 25:
            scores[InvestmentStyle.HIGH_RISK_VOLATILE] += 2
        
        # 2. 단기 변동형 판별
        if volatility_level == "high" or volume_change_rate > 100:
            scores[InvestmentStyle.SHORT_TERM_VOLATILE] += 3
        if volatility_level != "high" and volume_change_rate > 50:
            scores[InvestmentStyle.SHORT_TERM_VOLATILE] += 2
        
        # 3. 추세 안정형 판별
        if current_price > 0 and ma5 > 0 and ma20 > 0 and ma60 > 0:
            # 명확한 추세 확인
            if (current_price > ma5 > ma20 > ma60) or (current_price < ma5 < ma20 < ma60):
                scores[InvestmentStyle.TREND_STABLE] += 4
            if volatility_level == "normal":
                scores[InvestmentStyle.TREND_STABLE] += 2
        
        # 4. 실적 성장형 판별
        if earnings_growth > 20:  # 20% 이상 성장
            scores[InvestmentStyle.EARNINGS_GROWTH] += 5
        if per > 0 and per < 15:  # 저PER
            scores[InvestmentStyle.EARNINGS_GROWTH] += 3
        if roe > 15:  # 높은 ROE
            scores[InvestmentStyle.EARNINGS_GROWTH] += 3
        if institution_net > 0:
            scores[InvestmentStyle.EARNINGS_GROWTH] += 2
        
        # 5. 테마 순환형 판별
        if theme_strength == "strong":
            scores[InvestmentStyle.THEME_CYCLICAL] += 4
        if news_sentiment == "positive" and theme_strength in ["strong", "moderate"]:
            scores[InvestmentStyle.THEME_CYCLICAL] += 3
        if volume_change_rate > 50 and theme_strength in ["strong", "moderate"]:
            scores[InvestmentStyle.THEME_CYCLICAL] += 2
        
        # 6. 저변동 안정형 판별
        if volatility_level == "low":
            scores[InvestmentStyle.LOW_VOLATILITY_STABLE] += 4
        if per > 0 and 12 < per < 20:  # 중간 PER
            scores[InvestmentStyle.LOW_VOLATILITY_STABLE] += 2
        if earnings_growth > 0 and earnings_growth < 10:  # 안정적 성장
            scores[InvestmentStyle.LOW_VOLATILITY_STABLE] += 2
        
        # 최고 점수 스타일 결정
        best_style = max(scores, key=scores.get)
        best_score = scores[best_style]
        
        # 상위 3개 스타일
        sorted_styles = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 결과 생성
        style_info = cls.STYLE_DEFINITIONS[best_style]
        
        result = {
            "primary_style": {
                "style": best_style.value,
                "display_name": style_info.display_name,
                "description": style_info.description,
                "emoji": style_info.emoji,
                "score": best_score
            },
            "characteristics": style_info.characteristics,
            "suitable_investor": style_info.suitable_investor_type,
            "risk_level": style_info.risk_level,
            "profit_potential": style_info.profit_potential,
            "key_points": style_info.key_points,
            "beginner_comment": style_info.beginner_comment,
            "all_scores": {style.value: score for style, score in sorted_styles},
            "confidence": cls._calculate_confidence(best_score, sorted_styles)
        }
        
        return result
    
    @staticmethod
    def _calculate_confidence(best_score: int, sorted_styles: list) -> str:
        """
        스타일 판별 신뢰도 계산
        
        Args:
            best_score: 최고 점수
            sorted_styles: 정렬된 스타일 점수
            
        Returns:
            신뢰도 문구
        """
        if len(sorted_styles) > 1:
            second_score = sorted_styles[1][1]
            diff = best_score - second_score
            
            if diff >= 5:
                return "높음 (명확한 스타일)"
            elif diff >= 2:
                return "보통 (어느 정도 명확)"
            else:
                return "낮음 (스타일이 섞여 있음)"
        return "높음"
    
    @classmethod
    def get_investment_style_description(cls, style: str) -> Dict[str, Any]:
        """
        투자 스타일에 대한 상세 설명 반환
        
        Args:
            style: 스타일명
            
        Returns:
            스타일 상세 정보
        """
        for style_enum, info in cls.STYLE_DEFINITIONS.items():
            if style_enum.value == style:
                return {
                    "style": style,
                    "display_name": info.display_name,
                    "description": info.description,
                    "characteristics": info.characteristics,
                    "suitable_investor_type": info.suitable_investor_type,
                    "risk_level": info.risk_level,
                    "profit_potential": info.profit_potential,
                    "key_points": info.key_points,
                    "beginner_comment": info.beginner_comment,
                    "emoji": info.emoji
                }
        return {}
    
    @classmethod
    def get_risk_recommendation(cls, style: str) -> Dict[str, Any]:
        """
        투자 스타일별 위험도 및 권장사항
        
        Args:
            style: 스타일명
            
        Returns:
            위험도 및 권장사항
        """
        for style_enum, info in cls.STYLE_DEFINITIONS.items():
            if style_enum.value == style:
                recommendations = {
                    "저변동_안정형": [
                        "초보자도 상대적으로 안전합니다",
                        "장기 보유에 적합합니다",
                        "배당금 수익을 기대할 수 있습니다"
                    ],
                    "추세_안정형": [
                        "기술적 분석이 유용합니다",
                        "추세를 따라가는 투자 방식을 추천합니다",
                        "추세 반전에 주의하세요"
                    ],
                    "실적_성장형": [
                        "회사 실적을 꾸준히 확인하세요",
                        "장기 투자 관점을 가지세요",
                        "실적 발표 전 변동성이 증가할 수 있습니다"
                    ],
                    "단기_변동형": [
                        "충분한 경험을 바탕으로 투자하세요",
                        "손절/익절 계획을 미리 세우세요",
                        "손실 가능성을 충분히 이해하세요"
                    ],
                    "테마_순환형": [
                        "테마 흐름을 지속적으로 모니터링하세요",
                        "테마 약세가 시작되면 빠른 결정이 중요합니다",
                        "시장 심리 변화에 민감하세요"
                    ],
                    "고위험_변동형": [
                        "⚠️ 투자금 손실 가능성이 매우 높습니다",
                        "전체 자산의 작은 부분만 투자하세요",
                        "초보자는 피하는 것을 권장합니다",
                        "반드시 손절 계획을 세우세요"
                    ]
                }
                
                return {
                    "style": style,
                    "risk_level": info.risk_level,
                    "profit_potential": info.profit_potential,
                    "recommendations": recommendations.get(style, []),
                    "disclaimer": "본 조언은 참고용이며, 투자 결정은 본인 책임입니다."
                }
        return {}


# 싱글톤 인스턴스
investment_style_analyzer = InvestmentStyleAnalysisService()
