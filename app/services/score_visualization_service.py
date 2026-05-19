"""
점수 시각화 시스템
숫자 대신 시각적으로 이해 가능하게 구성
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class GaugeLevel(Enum):
    """게이지 레벨"""
    VERY_LOW = "매우 낮음"
    LOW = "낮음"
    MEDIUM = "보통"
    HIGH = "높음"
    VERY_HIGH = "매우 높음"


@dataclass
class GaugeVisualization:
    """게이지 시각화"""
    label: str
    value: float  # 0-100
    gauge_bars: str  # 시각화 바 (████░░░░░░)
    percentage: str  # "45%"
    level: GaugeLevel
    description: str
    color_code: str  # 색상 코드 (green, yellow, red, etc)
    emoji: str
    beginner_comment: str


class ScoreVisualizationService:
    """점수 시각화 서비스"""
    
    # 점수 구간 정의
    SCORE_RANGES = {
        "trend_strength": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["red", "orange", "yellow", "lightgreen", "green"],
            "labels": ["약함", "약중간", "중간", "강중간", "강함"]
        },
        "volatility": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["green", "lightgreen", "yellow", "orange", "red"],
            "labels": ["안정", "낮음", "보통", "높음", "매우높음"]
        },
        "risk_level": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["green", "lightgreen", "yellow", "orange", "red"],
            "labels": ["안전", "저위험", "중간", "고위험", "매우고위험"]
        },
        "volume_flow": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["gray", "blue", "lightblue", "lightgreen", "green"],
            "labels": ["관심낮음", "관심약함", "관심중간", "관심높음", "관심매우높음"]
        },
        "market_interest": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["gray", "blue", "lightblue", "lightgreen", "green"],
            "labels": ["낮음", "약함", "중간", "높음", "매우높음"]
        },
        "theme_strength": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["red", "orange", "yellow", "lightgreen", "green"],
            "labels": ["매우약함", "약함", "중간", "강함", "매우강함"]
        },
        "supply_flow": {
            "min": 0,
            "max": 100,
            "thresholds": [20, 40, 60, 80],
            "colors": ["red", "orange", "yellow", "lightgreen", "green"],
            "labels": ["매도우위", "약매도", "중립", "약매수", "매수우위"]
        }
    }
    
    @classmethod
    def create_gauge_visualization(
        cls,
        label: str,
        value: float,
        min_val: float = 0,
        max_val: float = 100,
        metric_type: str = "general"
    ) -> GaugeVisualization:
        """
        게이지 시각화 생성
        
        Args:
            label: 레이블 (예: "추세 강도")
            value: 값 (0-100)
            min_val: 최소값
            max_val: 최대값
            metric_type: 메트릭 유형 (trend_strength, volatility 등)
            
        Returns:
            게이지 시각화 객체
        """
        # 값을 0-100 범위로 정규화
        normalized_value = max(min_val, min(max_val, value))
        percentage = (normalized_value - min_val) / (max_val - min_val) * 100
        
        # 게이지 바 생성 (10칸)
        filled = int(percentage / 10)
        gauge_bars = "█" * filled + "░" * (10 - filled)
        
        # 레벨 및 색상 결정
        score_range = cls.SCORE_RANGES.get(metric_type, cls.SCORE_RANGES["trend_strength"])
        level_info = cls._determine_level(percentage, score_range)
        
        # 메트릭별 특화 코멘트
        beginner_comment = cls._generate_beginner_comment(
            label, percentage, metric_type
        )
        
        return GaugeVisualization(
            label=label,
            value=normalized_value,
            gauge_bars=gauge_bars,
            percentage=f"{percentage:.0f}%",
            level=level_info["level"],
            description=level_info["label"],
            color_code=level_info["color"],
            emoji=level_info["emoji"],
            beginner_comment=beginner_comment
        )
    
    @staticmethod
    def _determine_level(percentage: float, score_range: Dict) -> Dict[str, Any]:
        """
        점수에 따른 레벨 결정
        
        Args:
            percentage: 0-100 범위의 백분율
            score_range: 점수 범위 정의
            
        Returns:
            레벨 정보 딕셔너리
        """
        thresholds = score_range["thresholds"]
        colors = score_range["colors"]
        labels = score_range["labels"]
        
        # 적절한 구간 찾기
        if percentage < thresholds[0]:
            color = colors[0]
            label = labels[0]
            level = GaugeLevel.VERY_LOW
            emoji = "🔴"
        elif percentage < thresholds[1]:
            color = colors[1]
            label = labels[1]
            level = GaugeLevel.LOW
            emoji = "🟠"
        elif percentage < thresholds[2]:
            color = colors[2]
            label = labels[2]
            level = GaugeLevel.MEDIUM
            emoji = "🟡"
        elif percentage < thresholds[3]:
            color = colors[3]
            label = labels[3]
            level = GaugeLevel.HIGH
            emoji = "🟢"
        else:
            color = colors[4]
            label = labels[4]
            level = GaugeLevel.VERY_HIGH
            emoji = "🟢"
        
        return {
            "color": color,
            "label": label,
            "level": level,
            "emoji": emoji
        }
    
    @staticmethod
    def _generate_beginner_comment(label: str, percentage: float, metric_type: str) -> str:
        """
        초보자 친화형 코멘트 생성
        
        Args:
            label: 레이블
            percentage: 백분율
            metric_type: 메트릭 유형
            
        Returns:
            코멘트
        """
        comments = {
            "trend_strength": {
                "low": "현재 추세 강도가 약해서 가격 방향이 불명확합니다.",
                "medium": "중간 수준의 추세가 형성되어 있습니다.",
                "high": "강한 추세가 형성되어 있어 방향성이 명확합니다."
            },
            "volatility": {
                "low": "가격이 안정적으로 움직이고 있습니다.",
                "medium": "적정 수준의 변동성을 보이고 있습니다.",
                "high": "주가 등락폭이 커서 주의가 필요합니다."
            },
            "risk_level": {
                "low": "상대적으로 위험도가 낮은 상태입니다.",
                "medium": "중간 수준의 위험을 가지고 있습니다.",
                "high": "높은 위험을 내포하고 있으므로 주의가 필요합니다."
            },
            "volume_flow": {
                "low": "시장 관심도가 낮아 거래량이 적습니다.",
                "medium": "적정 수준의 거래량을 보이고 있습니다.",
                "high": "거래량이 증가해서 시장 관심도가 높아지는 중입니다."
            },
            "market_interest": {
                "low": "시장에서 주목도가 낮습니다.",
                "medium": "시장의 관심도가 적정 수준입니다.",
                "high": "시장에서 높은 관심을 받고 있습니다."
            },
            "theme_strength": {
                "low": "속한 테마가 약세이므로 악영향을 받을 수 있습니다.",
                "medium": "테마 흐름이 중립적입니다.",
                "high": "속한 테마가 강세여서 긍정적 영향을 받고 있습니다."
            },
            "supply_flow": {
                "low": "매도 세력이 우위인 상태입니다.",
                "medium": "수급이 균형을 이루고 있습니다.",
                "high": "매수 세력이 우위인 상태입니다."
            }
        }
        
        # 강도 결정
        if percentage < 40:
            strength = "low"
        elif percentage < 60:
            strength = "medium"
        else:
            strength = "high"
        
        metric_comments = comments.get(metric_type, comments["trend_strength"])
        return metric_comments.get(strength, "정상 범위 내입니다.")
    
    @classmethod
    def create_multiple_gauges(
        cls,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, GaugeVisualization]:
        """
        여러 게이지 한번에 생성
        
        Args:
            analysis_data: 분석 데이터
            
        Returns:
            게이지 시각화 딕셔너리
        """
        gauges = {}
        
        # 추세 강도
        trend_value = cls._calculate_trend_strength(analysis_data)
        gauges["trend_strength"] = cls.create_gauge_visualization(
            "추세 강도",
            trend_value,
            metric_type="trend_strength"
        )
        
        # 위험도
        risk_value = cls._calculate_risk_level(analysis_data)
        gauges["risk_level"] = cls.create_gauge_visualization(
            "위험도",
            risk_value,
            metric_type="risk_level"
        )
        
        # 거래량 흐름
        volume_value = cls._calculate_volume_flow(analysis_data)
        gauges["volume_flow"] = cls.create_gauge_visualization(
            "거래량 흐름",
            volume_value,
            metric_type="volume_flow"
        )
        
        # 시장 관심도
        interest_value = cls._calculate_market_interest(analysis_data)
        gauges["market_interest"] = cls.create_gauge_visualization(
            "시장 관심도",
            interest_value,
            metric_type="market_interest"
        )
        
        # 테마 강도
        theme_value = cls._calculate_theme_strength(analysis_data)
        gauges["theme_strength"] = cls.create_gauge_visualization(
            "테마 강도",
            theme_value,
            metric_type="theme_strength"
        )
        
        # 수급 흐름
        supply_value = cls._calculate_supply_flow(analysis_data)
        gauges["supply_flow"] = cls.create_gauge_visualization(
            "수급 흐름",
            supply_value,
            metric_type="supply_flow"
        )
        
        return gauges
    
    @staticmethod
    def _calculate_trend_strength(analysis_data: Dict[str, Any]) -> float:
        """추세 강도 계산"""
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        
        if not all([current_price, ma5, ma20, ma60]):
            return 50
        
        # 이동평균선 정렬 상태 확인
        if current_price > ma5 > ma20 > ma60:
            return 95  # 강한 상승
        elif ma5 > ma20 > ma60:
            return 75  # 중간~강한 상승
        elif current_price < ma5 < ma20 < ma60:
            return 5  # 강한 하락
        elif ma5 < ma20 < ma60:
            return 25  # 중간~강한 하락
        else:
            return 50  # 중립
    
    @staticmethod
    def _calculate_risk_level(analysis_data: Dict[str, Any]) -> float:
        """위험도 계산 (높을수록 위험)"""
        risk_score = 50  # 기본값
        
        volatility = analysis_data.get("volatility_level", "normal")
        rsi = analysis_data.get("rsi", 50)
        volume_change = analysis_data.get("volume_change_rate", 0)
        
        # 변동성에 따른 위험도
        if volatility == "high":
            risk_score += 30
        elif volatility == "low":
            risk_score -= 10
        
        # RSI에 따른 위험도
        if rsi > 75 or rsi < 25:
            risk_score += 20
        
        # 거래량 급증은 위험
        if volume_change > 300:
            risk_score += 15
        
        return min(100, max(0, risk_score))
    
    @staticmethod
    def _calculate_volume_flow(analysis_data: Dict[str, Any]) -> float:
        """거래량 흐름 계산"""
        volume_change = analysis_data.get("volume_change_rate", 0)
        
        # 거래량 증가율을 0-100으로 변환
        if volume_change <= 0:
            return 20
        elif volume_change < 50:
            return 40
        elif volume_change < 100:
            return 60
        elif volume_change < 200:
            return 80
        else:
            return 100
    
    @staticmethod
    def _calculate_market_interest(analysis_data: Dict[str, Any]) -> float:
        """시장 관심도 계산"""
        volume_change = analysis_data.get("volume_change_rate", 0)
        news_count = analysis_data.get("news_count", 0)
        theme_strength = analysis_data.get("theme_strength", "weak")
        
        interest = 50
        
        if volume_change > 100:
            interest += 20
        elif volume_change > 50:
            interest += 10
        
        if news_count > 5:
            interest += 20
        elif news_count > 0:
            interest += 10
        
        if theme_strength == "strong":
            interest += 15
        elif theme_strength == "moderate":
            interest += 5
        
        return min(100, max(0, interest))
    
    @staticmethod
    def _calculate_theme_strength(analysis_data: Dict[str, Any]) -> float:
        """테마 강도 계산"""
        theme_strength = analysis_data.get("theme_strength", "weak")
        
        if theme_strength == "strong":
            return 85
        elif theme_strength == "moderate":
            return 55
        else:
            return 25
    
    @staticmethod
    def _calculate_supply_flow(analysis_data: Dict[str, Any]) -> float:
        """수급 흐름 계산 (50이 중립, 높을수록 매수 우위)"""
        foreign_net = analysis_data.get("foreign_net", 0)
        institution_net = analysis_data.get("institution_net", 0)
        
        supply_score = 50
        
        # 외국인/기관 순매수는 최대 25씩 추가
        if foreign_net > 0:
            supply_score += min(25, foreign_net / 10000)  # 스케일 조정
        else:
            supply_score -= min(25, abs(foreign_net) / 10000)
        
        if institution_net > 0:
            supply_score += min(25, institution_net / 10000)
        else:
            supply_score -= min(25, abs(institution_net) / 10000)
        
        return min(100, max(0, supply_score))
    
    @classmethod
    def create_visual_summary(
        cls,
        gauges: Dict[str, GaugeVisualization]
    ) -> str:
        """
        게이지들의 시각적 요약 생성 (텍스트 형식)
        
        Args:
            gauges: 게이지 딕셔너리
            
        Returns:
            시각적 요약 문자열
        """
        summary = "\n📊 종목 상태 요약\n"
        summary += "=" * 40 + "\n\n"
        
        for key, gauge in gauges.items():
            summary += f"{gauge.emoji} {gauge.label}\n"
            summary += f"{gauge.gauge_bars} {gauge.percentage}\n"
            summary += f"상태: {gauge.description}\n"
            summary += f"📝 {gauge.beginner_comment}\n\n"
        
        return summary


# 싱글톤 인스턴스
score_visualizer = ScoreVisualizationService()
