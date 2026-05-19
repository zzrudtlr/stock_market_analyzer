"""
종목 한줄 요약 기능
종목을 한 문장으로 설명
"""

from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OneLineSummaryService:
    """종목 한줄 요약 서비스"""
    
    DISCLAIMER = "본 요약은 기술적 분석과 시장 데이터를 기반으로 생성된 참고용입니다."
    
    @staticmethod
    def generate_one_line_summary(
        stock_code: str,
        stock_name: str,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        종목을 한 줄로 요약
        
        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            analysis_data: 분석 데이터
            
        Returns:
            한줄 요약 및 추가 정보
        """
        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "one_line_summary": "",
            "summary_components": {},
            "generated_at": datetime.now().isoformat(),
            "disclaimer": OneLineSummaryService.DISCLAIMER
        }
        
        # 주요 특성 추출
        volume_surge = analysis_data.get("volume_change_rate", 0) > 100
        foreign_net = analysis_data.get("foreign_net", 0)
        institution_net = analysis_data.get("institution_net", 0)
        theme_strength = analysis_data.get("theme_strength", "weak")
        volatility = analysis_data.get("volatility_level", "normal")
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        
        # 1. 수급 특성
        supply_characteristic = ""
        if foreign_net > 0 and institution_net > 0:
            supply_characteristic = "외국인과 기관이 동시 순매수"
        elif foreign_net > 0:
            supply_characteristic = "외국인 순매수"
        elif institution_net > 0:
            supply_characteristic = "기관 순매수"
        elif foreign_net < 0 and institution_net < 0:
            supply_characteristic = "외국인과 기관 동시 순매도"
        else:
            supply_characteristic = "수급 균형"
        
        result["summary_components"]["supply"] = supply_characteristic
        
        # 2. 테마/거래량 특성
        theme_characteristic = ""
        if theme_strength == "strong":
            theme_characteristic = "강한 테마 흐름"
            if volume_surge:
                theme_characteristic += "과 거래량 증가"
        elif theme_strength == "moderate":
            theme_characteristic = "중간 테마 흐름"
        else:
            theme_characteristic = "약한 테마 흐름"
        
        result["summary_components"]["theme"] = theme_characteristic
        
        # 3. 추세 특성
        trend_characteristic = ""
        if current_price > 0 and ma5 > 0 and ma20 > 0 and ma60 > 0:
            if current_price > ma5 > ma20 > ma60:
                trend_characteristic = "강한 상승 추세"
            elif current_price > ma20 > ma60:
                trend_characteristic = "중기 상승 추세"
            elif current_price < ma5 < ma20 < ma60:
                trend_characteristic = "강한 하락 추세"
            elif current_price < ma20 < ma60:
                trend_characteristic = "중기 하락 추세"
            else:
                trend_characteristic = "혼합 추세"
        else:
            trend_characteristic = "추세 형성 중"
        
        result["summary_components"]["trend"] = trend_characteristic
        
        # 4. 변동성 특성
        volatility_characteristic = ""
        if volatility == "high":
            volatility_characteristic = "높은 변동성"
        elif volatility == "low":
            volatility_characteristic = "낮은 변동성"
        else:
            volatility_characteristic = "적정 변동성"
        
        result["summary_components"]["volatility"] = volatility_characteristic
        
        # 5. 한줄 요약 조합
        summary_parts = []
        
        # 수급이 명확하면 우선 표시
        if supply_characteristic != "수급 균형":
            summary_parts.append(supply_characteristic)
        
        # 테마가 강하면 표시
        if "강한" in theme_characteristic:
            summary_parts.append(theme_characteristic)
        
        # 추세가 명확하면 표시
        if "상승" in trend_characteristic or "하락" in trend_characteristic:
            summary_parts.append(trend_characteristic)
        
        # 변동성이 높으면 표시
        if "높은" in volatility_characteristic:
            summary_parts.append(volatility_characteristic)
        
        # 최종 한줄 요약 생성
        if not summary_parts:
            summary_parts = [supply_characteristic, theme_characteristic]
        
        result["one_line_summary"] = OneLineSummaryService._build_summary_sentence(
            summary_parts
        )
        
        return result
    
    @staticmethod
    def _build_summary_sentence(components: list) -> str:
        """
        요약 컴포넌트들을 자연스러운 문장으로 조합
        
        Args:
            components: 요약 컴포넌트 리스트
            
        Returns:
            조합된 문장
        """
        if not components:
            return "종목의 특성을 파악하는 중입니다."
        
        if len(components) == 1:
            return f"{components[0]} 흐름이 관찰됩니다."
        
        if len(components) == 2:
            return f"{components[0]}과 함께 {components[1]} 흐름이 진행 중입니다."
        
        # 3개 이상
        main_parts = components[:-1]
        last_part = components[-1]
        main_text = ", ".join(main_parts)
        return f"{main_text}과 함께 {last_part} 특성을 보이고 있습니다."
    
    @staticmethod
    def generate_beginner_friendly_summary(
        stock_code: str,
        stock_name: str,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        초보자를 위한 한줄 요약 생성 (더 간단한 버전)
        
        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            analysis_data: 분석 데이터
            
        Returns:
            초보자 친화형 요약
        """
        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "beginner_summary": "",
            "what_to_note": [],
            "generated_at": datetime.now().isoformat()
        }
        
        # 주요 신호들 추출
        signals = []
        
        # 긍정 신호
        foreign_net = analysis_data.get("foreign_net", 0)
        if foreign_net > 0:
            signals.append(("positive", "외국인이 사고 있어요"))
        
        institution_net = analysis_data.get("institution_net", 0)
        if institution_net > 0:
            signals.append(("positive", "기관이 사고 있어요"))
        
        volume_change = analysis_data.get("volume_change_rate", 0)
        if volume_change > 100:
            signals.append(("positive", "거래량이 많아져요"))
        
        theme_strength = analysis_data.get("theme_strength", "weak")
        if theme_strength == "strong":
            signals.append(("positive", "인기 있는 테마 중입니다"))
        
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        if current_price > ma5 > ma20:
            signals.append(("positive", "상승 흐름이 보여요"))
        
        # 위험 신호
        rsi = analysis_data.get("rsi", 50)
        if rsi > 75:
            signals.append(("negative", "과하게 올랐어요"))
        elif rsi < 25:
            signals.append(("negative", "과하게 내렸어요"))
        
        volatility = analysis_data.get("volatility_level", "normal")
        if volatility == "high":
            signals.append(("negative", "등락이 커요"))
        
        if foreign_net < 0:
            signals.append(("negative", "외국인이 팔고 있어요"))
        
        if theme_strength == "weak":
            signals.append(("negative", "테마 흐름이 약해요"))
        
        # 요약 생성
        positive_signals = [s[1] for s in signals if s[0] == "positive"]
        negative_signals = [s[1] for s in signals if s[0] == "negative"]
        
        summary_text = f"{stock_name}은 "
        
        if positive_signals and not negative_signals:
            summary_text += f"{', '.join(positive_signals)}는 좋은 신호들이 보입니다."
        elif negative_signals and not positive_signals:
            summary_text += f"{', '.join(negative_signals)}으로 주의가 필요합니다."
        elif positive_signals and negative_signals:
            summary_text += f"긍정 신호({', '.join(positive_signals)})와 위험 신호({', '.join(negative_signals)})가 섞여 있습니다."
        else:
            summary_text += "현재 특별한 신호가 보이지 않습니다."
        
        result["beginner_summary"] = summary_text
        
        # 주의할 점
        if negative_signals:
            result["what_to_note"] = negative_signals
        
        return result
    
    @staticmethod
    def generate_multiple_summaries(stocks_data: list) -> list:
        """
        여러 종목의 한줄 요약 생성
        
        Args:
            stocks_data: [(stock_code, stock_name, analysis_data), ...] 리스트
            
        Returns:
            한줄 요약 리스트
        """
        summaries = []
        
        for stock_code, stock_name, analysis_data in stocks_data:
            summary = OneLineSummaryService.generate_one_line_summary(
                stock_code, stock_name, analysis_data
            )
            summaries.append(summary)
        
        return summaries


# 싱글톤 인스턴스
one_line_summarizer = OneLineSummaryService()
