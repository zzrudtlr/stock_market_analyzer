"""
초보자용 AI 설명 변환 기능
복잡한 분석 데이터를 초보자가 이해하기 쉬운 자연어로 변환
"""

from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BeginnerAIExplainerService:
    """초보자를 위한 AI 설명 서비스"""
    
    DISCLAIMER = "본 설명은 가격, 거래량, 수급, 뉴스, 추세 데이터를 기반으로 생성된 참고용 분석입니다. 투자 판단은 사용자 본인 책임입니다."
    
    @staticmethod
    def generate_beginner_summary(
        stock_code: str,
        stock_name: str,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        복잡한 분석 데이터를 초보자 친화형 요약으로 변환
        
        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            analysis_data: 분석 데이터 (거래량, MA, RSI, 수급 등)
            
        Returns:
            초보자 친화형 설명 딕셔너리
        """
        summary = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "generated_at": datetime.now().isoformat(),
            "beginner_summary": "",
            "beginner_positive_comment": "",
            "beginner_risk_comment": "",
            "beginner_market_comment": "",
            "key_points": [],
            "disclaimer": BeginnerAIExplainerService.DISCLAIMER
        }
        
        # 분석 데이터 추출
        rsi = analysis_data.get("rsi", 50)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        current_price = analysis_data.get("current_price", 0)
        volume_change_rate = analysis_data.get("volume_change_rate", 0)  # 거래량 증가율 %
        foreign_net = analysis_data.get("foreign_net", 0)  # 외국인 순매수
        institution_net = analysis_data.get("institution_net", 0)  # 기관 순매수
        news_sentiment = analysis_data.get("news_sentiment", "neutral")  # positive, negative, neutral
        theme_strength = analysis_data.get("theme_strength", "weak")  # strong, moderate, weak
        volatility_level = analysis_data.get("volatility_level", "normal")  # high, normal, low
        
        # 주요 포인트 수집
        key_points = []
        
        # 거래량 분석
        if volume_change_rate > 100:
            key_points.append(f"거래량이 {volume_change_rate:.0f}% 증가했습니다")
            summary["beginner_summary"] += "거래량이 평소보다 크게 증가하여 시장 관심도가 높아진 상태입니다. "
        elif volume_change_rate > 50:
            key_points.append(f"거래량이 {volume_change_rate:.0f}% 증가 중입니다")
            summary["beginner_summary"] += "거래량이 평소보다 증가하여 시장 관심도가 높아지는 중입니다. "
        
        # 이동평균선 분석
        if current_price > ma5 > ma20 > ma60:
            key_points.append("단기/중기/장기 모두 상승 흐름입니다")
            summary["beginner_summary"] += "단기부터 장기까지 모두 상승 추세를 보이고 있습니다. "
        elif current_price > ma20 > ma60:
            key_points.append("중기와 장기 상승 흐름입니다")
            summary["beginner_summary"] += "중기 이상의 상승 추세가 형성되어 있습니다. "
        elif current_price < ma20 < ma60:
            key_points.append("중기와 장기 하락 흐름입니다")
            summary["beginner_summary"] += "중기 이상의 하락 추세가 계속되고 있습니다. "
        
        # RSI 분석
        if rsi > 75:
            key_points.append("단기 과열 상태입니다")
            summary["beginner_risk_comment"] += "현재 주가가 단기적으로 과도하게 오른 상태일 수 있습니다. "
        elif rsi < 25:
            key_points.append("단기 과도 하락 상태입니다")
            summary["beginner_risk_comment"] += "현재 주가가 단기적으로 과도하게 내린 상태일 수 있습니다. "
        elif rsi > 60:
            summary["beginner_positive_comment"] += "단기 상승 강도가 양호한 상태입니다. "
        
        # 수급 분석
        if foreign_net > 0:
            key_points.append("외국인이 순매수 중입니다")
            summary["beginner_positive_comment"] += "외국인 투자자들이 매수하고 있습니다. "
        elif foreign_net < 0:
            key_points.append("외국인이 순매도 중입니다")
            summary["beginner_risk_comment"] += "외국인 투자자들이 매도하고 있습니다. "
        
        if institution_net > 0:
            key_points.append("기관이 순매수 중입니다")
            summary["beginner_positive_comment"] += "국내 기관투자자들이 매수하고 있습니다. "
        
        # 뉴스/테마 분석
        if news_sentiment == "positive":
            summary["beginner_market_comment"] += "시장에서 긍정적인 뉴스가 주목받고 있습니다. "
            key_points.append("긍정적인 뉴스가 있습니다")
        elif news_sentiment == "negative":
            summary["beginner_risk_comment"] += "부정적인 뉴스 영향이 있습니다. "
            key_points.append("부정적인 뉴스가 있습니다")
        
        if theme_strength == "strong":
            summary["beginner_positive_comment"] += "속한 테마가 시장에서 강세를 보이고 있습니다. "
            key_points.append("강한 테마 흐름입니다")
        elif theme_strength == "weak":
            summary["beginner_risk_comment"] += "테마 흐름이 약해지는 중입니다. "
            key_points.append("약한 테마 흐름입니다")
        
        # 변동성 분석
        if volatility_level == "high":
            summary["beginner_risk_comment"] += "주가 등락폭이 크므로 주의가 필요합니다. "
            key_points.append("변동성이 높은 상태입니다")
        
        # 최종 요약 정리
        if not summary["beginner_positive_comment"]:
            summary["beginner_positive_comment"] = "특별히 강한 긍정 신호는 보이지 않습니다. "
        
        if not summary["beginner_risk_comment"]:
            summary["beginner_risk_comment"] = "특별한 위험 신호는 보이지 않습니다. "
        
        if not summary["beginner_market_comment"]:
            summary["beginner_market_comment"] = "시장 흐름을 중립적으로 봅니다. "
        
        summary["key_points"] = key_points
        
        return summary
    
    @staticmethod
    def generate_beginner_explanation_for_analysis(
        analysis_type: str,
        analysis_result: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        특정 분석 결과를 초보자가 이해할 수 있게 설명
        
        Args:
            analysis_type: 분석 유형 (chart_pattern, fundamental, news_sentiment 등)
            analysis_result: 분석 결과 딕셔너리
            
        Returns:
            초보자 친화형 설명
        """
        explanation = {
            "analysis_type": analysis_type,
            "beginner_explanation": "",
            "what_it_means": "",
            "why_it_matters": "",
            "example": "",
            "disclaimer": BeginnerAIExplainerService.DISCLAIMER
        }
        
        if analysis_type == "chart_pattern":
            pattern = analysis_result.get("pattern", "unknown")
            confidence = analysis_result.get("confidence", 0)
            
            if pattern == "double_top":
                explanation["beginner_explanation"] = "차트에 'V자' 같은 패턴이 보입니다."
                explanation["what_it_means"] = "가격이 두 번 같은 높이까지 올라갔다가 내려오는 형태입니다."
                explanation["why_it_matters"] = "이 패턴 이후 가격이 더 내려갈 가능성을 참고합니다."
                explanation["example"] = "예: 5월에 50,000원 / 6월에 50,000원 / 그 후 내려감"
            
            elif pattern == "double_bottom":
                explanation["beginner_explanation"] = "차트에 'U자' 같은 패턴이 보입니다."
                explanation["what_it_means"] = "가격이 두 번 같은 낮이까지 내려갔다가 올라오는 형태입니다."
                explanation["why_it_matters"] = "이 패턴 이후 가격이 올라갈 가능성을 참고합니다."
                explanation["example"] = "예: 5월에 40,000원 / 6월에 40,000원 / 그 후 올라감"
            
            explanation["analysis_type"] = f"{analysis_type} (신뢰도: {confidence:.0f}%)"
        
        elif analysis_type == "fundamental":
            metric = analysis_result.get("metric", "unknown")
            value = analysis_result.get("value", 0)
            rating = analysis_result.get("rating", "unknown")
            
            if metric == "PER":
                explanation["beginner_explanation"] = f"PER는 {value:.1f}배입니다."
                explanation["what_it_means"] = f"현재 주가가 연간 순이익의 {value:.1f}배 수준입니다."
                if value < 10:
                    explanation["why_it_matters"] = "낮은 수준으로 상대적으로 저평가되어 있을 수 있습니다."
                elif value > 25:
                    explanation["why_it_matters"] = "높은 수준으로 시장이 높게 평가하고 있습니다."
                else:
                    explanation["why_it_matters"] = "평균적인 수준입니다."
            
            elif metric == "PBR":
                explanation["beginner_explanation"] = f"PBR은 {value:.2f}배입니다."
                explanation["what_it_means"] = f"주가가 자산가치의 {value:.2f}배 수준입니다."
                if value < 1.0:
                    explanation["why_it_matters"] = "자산 가치보다 저렴하게 거래 중입니다."
                else:
                    explanation["why_it_matters"] = f"자산 가치의 {value:.2f}배로 평가받고 있습니다."
        
        elif analysis_type == "news_sentiment":
            sentiment = analysis_result.get("sentiment", "neutral")
            count = analysis_result.get("count", 0)
            
            if sentiment == "positive":
                explanation["beginner_explanation"] = f"최근 {count}건의 긍정적인 뉴스가 있습니다."
                explanation["what_it_means"] = "시장에서 좋은 소식을 받고 있는 상태입니다."
                explanation["why_it_matters"] = "긍정적인 뉴스는 주가 상승으로 이어질 수 있습니다."
            elif sentiment == "negative":
                explanation["beginner_explanation"] = f"최근 {count}건의 부정적인 뉴스가 있습니다."
                explanation["what_it_means"] = "시장에서 좋지 않은 소식을 받고 있는 상태입니다."
                explanation["why_it_matters"] = "부정적인 뉴스는 주가 하락으로 이어질 수 있습니다."
            else:
                explanation["beginner_explanation"] = "최근 특별한 뉴스 영향은 보이지 않습니다."
                explanation["what_it_means"] = "시장은 중립적인 상태입니다."
        
        return explanation
    
    @staticmethod
    def generate_investment_style_comment(style: str) -> str:
        """
        투자 스타일을 설명하는 초보자 친화형 문구 생성
        
        Args:
            style: 투자 스타일 (예: "단기변동형", "추세안정형" 등)
            
        Returns:
            설명 문구
        """
        style_comments = {
            "단기_변동형": "변동성이 크고 단기 등락이 심한 유형입니다. 급등과 급락 가능성이 높으므로 주의가 필요합니다.",
            "추세_안정형": "명확한 추세를 보이며 비교적 안정적인 유형입니다. 추세 방향에 따라 흐름을 예측할 수 있습니다.",
            "실적_성장형": "실적 개선에 따라 가격이 움직이는 유형입니다. 장기 성장 가능성을 고려합니다.",
            "테마_순환형": "시장의 관심도에 따라 크게 영향을 받는 유형입니다. 테마 변화에 주의가 필요합니다.",
            "고위험_변동형": "매우 높은 변동성으로 큰 수익과 손실 모두 가능한 유형입니다. 충분한 이해와 위험 관리가 필수입니다.",
            "저변동_안정형": "변동성이 낮고 안정적인 유형입니다. 큰 수익 기회는 적지만 보수적 투자에 적합합니다.",
        }
        return style_comments.get(style, f"'{style}' 스타일의 종목입니다.")
    
    @staticmethod
    def generate_risk_warning(
        risk_level: str,
        risk_factors: list
    ) -> str:
        """
        위험도에 따른 경고 문구 생성
        
        Args:
            risk_level: 위험도 (low, medium, high)
            risk_factors: 위험 요인 리스트
            
        Returns:
            위험 경고 문구
        """
        warnings = {
            "high": "⚠️ 이 종목은 높은 위험을 내포하고 있습니다. ",
            "medium": "⚠️ 이 종목은 중간 수준의 위험을 가지고 있습니다. ",
            "low": "이 종목은 상대적으로 낮은 위험을 보이고 있습니다. "
        }
        
        warning = warnings.get(risk_level, "")
        if risk_factors:
            warning += f"주의할 점: {', '.join(risk_factors)}"
        
        warning += f"\n\n{BeginnerAIExplainerService.DISCLAIMER}"
        
        return warning


# 싱글톤 인스턴스
beginner_explainer = BeginnerAIExplainerService()
