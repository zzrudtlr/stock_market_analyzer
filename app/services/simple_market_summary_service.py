"""
시장 흐름 한줄 요약 기능
현재 시장 상태를 초보자도 이해하기 쉽게 요약
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SimpleMarketSummaryService:
    """시장 흐름 한줄 요약 서비스"""
    
    DISCLAIMER = "본 요약은 시장 데이터를 기반으로 생성된 참고용 분석입니다. 투자 판단은 사용자 본인 책임입니다."
    
    @staticmethod
    def generate_simple_market_summary(market_data: Dict[str, Any]) -> Dict[str, str]:
        """
        시장 전체 상태를 초보자 친화형 한줄 요약으로 생성
        
        Args:
            market_data: 시장 데이터 (지수, 테마, 수급 등)
            
        Returns:
            한줄 요약 및 상세 설명
        """
        result = {
            "summary_title": "오늘 시장 흐름",
            "simple_summary": "",
            "market_sentiment": "",
            "main_themes": [],
            "risk_signals": [],
            "key_points": [],
            "generated_at": datetime.now().isoformat(),
            "disclaimer": SimpleMarketSummaryService.DISCLAIMER
        }
        
        # 시장 지수 분석
        kospi_change = market_data.get("kospi_change", 0)
        kosdaq_change = market_data.get("kosdaq_change", 0)
        
        # 테마별 분석
        top_themes = market_data.get("top_themes", [])  # [(테마명, 강도), ...]
        weak_themes = market_data.get("weak_themes", [])
        
        # 수급 분석
        foreign_net_total = market_data.get("foreign_net_total", 0)
        institution_net_total = market_data.get("institution_net_total", 0)
        
        # 시장 심리
        market_sentiment = market_data.get("market_sentiment", "neutral")  # positive, negative, neutral
        volatility = market_data.get("market_volatility", "normal")
        
        # 기타
        volume_trend = market_data.get("volume_trend", "normal")
        news_tone = market_data.get("news_tone", "neutral")
        
        # 1. 기본 시장 방향성 파악
        if kospi_change > 1 and kosdaq_change > 1:
            market_trend = "상승"
            trend_emoji = "📈"
        elif kospi_change < -1 and kosdaq_change < -1:
            market_trend = "하락"
            trend_emoji = "📉"
        else:
            market_trend = "혼조"
            trend_emoji = "📊"
        
        # 2. 주요 테마 파악
        if top_themes:
            theme_names = [theme[0] for theme in top_themes[:2]]
            main_theme_str = ", ".join(theme_names)
            result["main_themes"] = theme_names
        else:
            main_theme_str = ""
        
        # 3. 기본 요약 생성
        base_summary = f"오늘 시장은 {market_trend} 흐름"
        
        # 테마 추가
        if main_theme_str:
            base_summary += f"으로, {main_theme_str} 중심의 자금이 들어오는 모습입니다."
        else:
            base_summary += "입니다."
        
        # 수급 추가
        if foreign_net_total > 0 and institution_net_total > 0:
            base_summary += " 외국인과 기관 모두 순매수하는 중입니다."
        elif foreign_net_total > 0:
            base_summary += " 외국인이 순매수하고 있습니다."
        elif institution_net_total > 0:
            base_summary += " 기관이 순매수하고 있습니다."
        elif foreign_net_total < 0 or institution_net_total < 0:
            base_summary += " 큰 자금의 이탈이 있습니다."
        
        result["simple_summary"] = base_summary
        
        # 4. 심리 상태
        if market_sentiment == "positive":
            sentiment_text = "시장 심리가 긍정적입니다."
        elif market_sentiment == "negative":
            sentiment_text = "시장 심리가 부정적입니다."
        else:
            sentiment_text = "시장 심리가 중립적입니다."
        
        result["market_sentiment"] = sentiment_text
        
        # 5. 키포인트 생성
        key_points = []
        
        if volatility == "high":
            key_points.append("⚠️ 변동성이 높은 날입니다 - 주의가 필요합니다")
        
        if volume_trend == "high":
            key_points.append("📊 거래량이 많아 자금 이동이 활발합니다")
        elif volume_trend == "low":
            key_points.append("📉 거래량이 적어 시장이 한산합니다")
        
        if top_themes and weak_themes:
            key_points.append(f"🔄 테마 로테이션이 일어나는 중입니다")
        
        if news_tone == "positive":
            key_points.append("📰 긍정적인 뉴스가 많습니다")
        elif news_tone == "negative":
            key_points.append("📰 부정적인 뉴스가 많습니다")
        
        result["key_points"] = key_points
        
        # 6. 위험 신호 파악
        risk_signals = []
        
        if market_sentiment == "negative" and volatility == "high":
            risk_signals.append("약세 + 높은 변동성: 신중한 자세 필요")
        
        if foreign_net_total < 0 and institution_net_total < 0:
            risk_signals.append("외국인/기관 동시 매도: 매물 주의")
        
        if weak_themes and not top_themes:
            risk_signals.append("주도 테마 부재: 방향성 불명확")
        
        if volatility == "high" and volume_trend == "low":
            risk_signals.append("높은 변동성 + 낮은 거래량: 기술적 약세")
        
        result["risk_signals"] = risk_signals
        
        return result
    
    @staticmethod
    def generate_today_hot_themes(market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        오늘 핫한 테마 요약
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            핫 테마 정보
        """
        top_themes = market_data.get("top_themes", [])
        
        result = {
            "title": "🔥 오늘 강한 테마",
            "themes": [],
            "generated_at": datetime.now().isoformat()
        }
        
        for idx, (theme_name, strength) in enumerate(top_themes[:5], 1):
            theme_info = {
                "rank": idx,
                "name": theme_name,
                "strength_level": strength,
                "description": SimpleMarketSummaryService._get_theme_description(theme_name),
                "strength_percentage": SimpleMarketSummaryService._strength_to_percentage(strength),
                "emoji": SimpleMarketSummaryService._get_theme_emoji(theme_name)
            }
            result["themes"].append(theme_info)
        
        return result
    
    @staticmethod
    def generate_today_weak_themes(market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        오늘 약한 테마 요약
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            약한 테마 정보
        """
        weak_themes = market_data.get("weak_themes", [])
        
        result = {
            "title": "❄️ 오늘 약한 테마",
            "themes": [],
            "caution": "이 테마 중심 종목은 약세이므로 주의가 필요합니다.",
            "generated_at": datetime.now().isoformat()
        }
        
        for idx, (theme_name, weakness) in enumerate(weak_themes[:5], 1):
            theme_info = {
                "rank": idx,
                "name": theme_name,
                "weakness_level": weakness,
                "description": SimpleMarketSummaryService._get_theme_description(theme_name),
                "weakness_percentage": SimpleMarketSummaryService._weakness_to_percentage(weakness),
                "emoji": "❌"
            }
            result["themes"].append(theme_info)
        
        return result
    
    @staticmethod
    def generate_market_outlook(market_data: Dict[str, Any]) -> Dict[str, str]:
        """
        시장 전망 생성 (단기)
        
        Args:
            market_data: 시장 데이터
            
        Returns:
            시장 전망 정보
        """
        kospi_change = market_data.get("kospi_change", 0)
        volatility = market_data.get("market_volatility", "normal")
        market_sentiment = market_data.get("market_sentiment", "neutral")
        
        result = {
            "title": "단기 시장 전망",
            "outlook_1day": "",
            "outlook_1week": "",
            "cautions": [],
            "opportunities": [],
            "disclaimer": SimpleMarketSummaryService.DISCLAIMER
        }
        
        # 1일 전망
        if kospi_change > 1:
            result["outlook_1day"] = "상승 모멘텀이 유지될 수 있습니다."
        elif kospi_change < -1:
            result["outlook_1day"] = "하락세가 계속될 수 있습니다. 주의가 필요합니다."
        else:
            result["outlook_1day"] = "혼조 흐름이 계속될 수 있습니다."
        
        # 1주 전망
        if market_sentiment == "positive":
            result["outlook_1week"] = "긍정 심리가 유지되면 상승이 지속될 수 있습니다."
        elif market_sentiment == "negative":
            result["outlook_1week"] = "부정 심리를 극복해야 회복이 가능합니다."
        else:
            result["outlook_1week"] = "시장이 방향을 결정할 때까지 혼조가 이어질 수 있습니다."
        
        # 주의사항
        if volatility == "high":
            result["cautions"].append("높은 변동성 주의: 손절/익절 계획 필요")
        
        if market_sentiment == "negative":
            result["cautions"].append("부정 심리: 신중한 자세 권장")
        
        # 기회 요소
        if kospi_change < -1 and volatility == "high":
            result["opportunities"].append("저점 매수 기회가 있을 수 있습니다")
        
        return result
    
    @staticmethod
    def _get_theme_description(theme_name: str) -> str:
        """테마별 설명"""
        descriptions = {
            "AI": "인공지능 관련 기술과 서비스가 주목받는 테마입니다.",
            "2차전지": "전기차 배터리 관련 종목들이 주목받는 테마입니다.",
            "반도체": "칩/반도체 관련 종목들이 주목받는 테마입니다.",
            "K-콘텐츠": "한국 엔터테인먼트 콘텐츠가 주목받는 테마입니다.",
            "우주항공": "우주 산업 관련 종목들이 주목받는 테마입니다.",
            "로봇": "로봇 관련 기술과 기업들이 주목받는 테마입니다.",
            "수소": "수소 에너지 관련 종목들이 주목받는 테마입니다.",
            "바이오": "생명공학 및 제약 관련 종목들이 주목받는 테마입니다.",
        }
        return descriptions.get(theme_name, f"{theme_name} 관련 종목들이 주목받고 있습니다.")
    
    @staticmethod
    def _strength_to_percentage(strength: str) -> str:
        """강도를 백분율로 변환"""
        strength_map = {
            "very_strong": "90~100%",
            "strong": "70~90%",
            "moderate": "50~70%",
            "weak": "30~50%",
            "very_weak": "0~30%"
        }
        return strength_map.get(strength, "50%")
    
    @staticmethod
    def _weakness_to_percentage(weakness: str) -> str:
        """약도를 백분율로 변환"""
        weakness_map = {
            "very_weak": "0~30%",
            "weak": "30~50%",
            "moderate": "50~70%",
            "strong": "70~90%",
            "very_strong": "90~100%"
        }
        return weakness_map.get(weakness, "50%")
    
    @staticmethod
    def _get_theme_emoji(theme_name: str) -> str:
        """테마별 이모지"""
        emoji_map = {
            "AI": "🤖",
            "2차전지": "🔋",
            "반도체": "💻",
            "K-콘텐츠": "🎬",
            "우주항공": "🚀",
            "로봇": "🦾",
            "수소": "⚛️",
            "바이오": "🧬",
        }
        return emoji_map.get(theme_name, "📈")


# 싱글톤 인스턴스
market_summary_service = SimpleMarketSummaryService()
