"""
과거 유사 패턴 비교 기능
현재 패턴과 과거 유사 패턴 비교 제공
"""

from typing import Dict, List, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import logging
import random

logger = logging.getLogger(__name__)


@dataclass
class HistoricalPattern:
    """과거 패턴 정보"""
    pattern_type: str  # 패턴 유형
    occurrence_date: str  # 발생 날짜
    duration_days: int  # 지속 기간
    outcome: str  # 결과 (uptrend, sideways, downtrend)
    outcome_percentage: float  # 결과 수익률
    similarity_score: float  # 현재 패턴과의 유사도
    description: str  # 설명


class PatternHistoryAnalysisService:
    """과거 유사 패턴 비교 서비스"""
    
    DISCLAIMER = "과거 패턴과 현재 패턴의 일치는 미래를 예측하지 않습니다. 참고용 분석일 뿐입니다."
    
    @staticmethod
    def analyze_similar_patterns(
        stock_code: str,
        current_pattern: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        현재 패턴과 유사한 과거 패턴 분석
        
        Args:
            stock_code: 종목 코드
            current_pattern: 현재 패턴 정보
            
        Returns:
            유사 패턴 분석 결과
        """
        result = {
            "stock_code": stock_code,
            "current_pattern": {
                "volume_surge": current_pattern.get("volume_surge", False),  # 거래량 급증
                "ma_crossover": current_pattern.get("ma_crossover", False),  # MA 교차
                "rsi_overbought": current_pattern.get("rsi_overbought", False),  # RSI 과열
                "strong_theme": current_pattern.get("strong_theme", False),  # 강한 테마
                "foreign_buying": current_pattern.get("foreign_buying", False),  # 외국인 순매수
                "price_change": current_pattern.get("price_change", 0)  # 가격 변화율
            },
            "similar_patterns_count": 0,
            "similar_patterns": [],
            "historical_statistics": {},
            "generated_at": datetime.now().isoformat(),
            "disclaimer": PatternHistoryAnalysisService.DISCLAIMER
        }
        
        # 현재 패턴 특성에 맞는 과거 패턴 찾기
        similar_patterns = PatternHistoryAnalysisService._find_similar_patterns(
            current_pattern
        )
        
        result["similar_patterns"] = similar_patterns
        result["similar_patterns_count"] = len(similar_patterns)
        
        # 통계 계산
        if similar_patterns:
            stats = PatternHistoryAnalysisService._calculate_pattern_statistics(
                similar_patterns
            )
            result["historical_statistics"] = stats
        
        return result
    
    @staticmethod
    def _find_similar_patterns(current_pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        과거 유사 패턴 찾기 (시뮬레이션 데이터)
        
        실제 구현에서는 데이터베이스에서 조회
        
        Args:
            current_pattern: 현재 패턴
            
        Returns:
            유사 패턴 리스트
        """
        # 시뮬레이션: 과거 데이터베이스에서 유사 패턴 조회
        # 실제로는 DB에서 조회하거나, CSV에서 읽어올 수 있음
        
        similar_patterns = []
        
        # 패턴 조합에 따른 유사 사례 생성
        pattern_key = (
            current_pattern.get("volume_surge", False),
            current_pattern.get("ma_crossover", False),
            current_pattern.get("rsi_overbought", False),
            current_pattern.get("strong_theme", False),
            current_pattern.get("foreign_buying", False),
        )
        
        # 패턴별 과거 사례
        pattern_cases = {
            (True, True, False, True, True): [
                {
                    "pattern_type": "거래량 급증 + 골든크로스 + 강한 테마 + 외국인 매수",
                    "occurrence_date": "2024-01-15",
                    "duration_days": 5,
                    "outcome": "uptrend",
                    "outcome_percentage": 15.2,
                    "similarity": 95,
                    "description": "강한 상승 신호들이 함께 나타난 경우"
                },
                {
                    "pattern_type": "거래량 급증 + 골든크로스 + 강한 테마 + 외국인 매수",
                    "occurrence_date": "2023-08-20",
                    "duration_days": 7,
                    "outcome": "uptrend",
                    "outcome_percentage": 22.5,
                    "similarity": 92,
                    "description": "더 장기간 상승한 사례"
                },
                {
                    "pattern_type": "거래량 급증 + 골든크로스 + 강한 테마 + 외국인 매수",
                    "occurrence_date": "2023-03-10",
                    "duration_days": 3,
                    "outcome": "sideways",
                    "outcome_percentage": -2.3,
                    "similarity": 88,
                    "description": "일부 조정을 받다가 횡보한 사례"
                },
            ],
            (True, False, True, True, False): [
                {
                    "pattern_type": "거래량 급증 + RSI 과열 + 강한 테마",
                    "occurrence_date": "2024-02-08",
                    "duration_days": 2,
                    "outcome": "downtrend",
                    "outcome_percentage": -8.5,
                    "similarity": 90,
                    "description": "과열 후 급락한 사례"
                },
                {
                    "pattern_type": "거래량 급증 + RSI 과열 + 강한 테마",
                    "occurrence_date": "2023-11-25",
                    "duration_days": 4,
                    "outcome": "sideways",
                    "outcome_percentage": 1.2,
                    "similarity": 87,
                    "description": "조정을 받고 회복한 사례"
                },
                {
                    "pattern_type": "거래량 급증 + RSI 과열 + 강한 테마",
                    "occurrence_date": "2023-06-15",
                    "duration_days": 1,
                    "outcome": "downtrend",
                    "outcome_percentage": -12.3,
                    "similarity": 85,
                    "description": "다음날 바로 급락한 사례"
                },
            ],
            (True, True, False, False, True): [
                {
                    "pattern_type": "거래량 급증 + 골든크로스 + 외국인 매수",
                    "occurrence_date": "2024-01-22",
                    "duration_days": 6,
                    "outcome": "uptrend",
                    "outcome_percentage": 18.3,
                    "similarity": 88,
                    "description": "지속적인 상승 신호"
                },
                {
                    "pattern_type": "거래량 급증 + 골든크로스 + 외국인 매수",
                    "occurrence_date": "2023-09-05",
                    "duration_days": 8,
                    "outcome": "uptrend",
                    "outcome_percentage": 25.7,
                    "similarity": 85,
                    "description": "장기 상승으로 이어진 사례"
                },
            ],
            (True, False, False, True, False): [
                {
                    "pattern_type": "거래량 급증 + 강한 테마",
                    "occurrence_date": "2024-02-10",
                    "duration_days": 4,
                    "outcome": "uptrend",
                    "outcome_percentage": 8.9,
                    "similarity": 80,
                    "description": "중간 수준의 상승"
                },
                {
                    "pattern_type": "거래량 급증 + 강한 테마",
                    "occurrence_date": "2023-07-18",
                    "duration_days": 3,
                    "outcome": "sideways",
                    "outcome_percentage": 0.5,
                    "similarity": 78,
                    "description": "거래량만으로는 방향성이 약한 경우"
                },
            ],
        }
        
        # 매칭되는 패턴 케이스 반환
        if pattern_key in pattern_cases:
            for case in pattern_cases[pattern_key]:
                similar_patterns.append({
                    "pattern_type": case["pattern_type"],
                    "occurrence_date": case["occurrence_date"],
                    "duration_days": case["duration_days"],
                    "outcome": case["outcome"],
                    "outcome_percentage": case["outcome_percentage"],
                    "similarity_score": case["similarity"],
                    "outcome_description": PatternHistoryAnalysisService._get_outcome_description(
                        case["outcome"],
                        case["outcome_percentage"]
                    ),
                    "description": case["description"]
                })
        else:
            # 기본 패턴 반환
            similar_patterns.append({
                "pattern_type": "혼합 패턴",
                "occurrence_date": "데이터 부족",
                "duration_days": 0,
                "outcome": "unknown",
                "outcome_percentage": 0,
                "similarity_score": 0,
                "outcome_description": "유사 패턴의 충분한 과거 데이터가 없습니다.",
                "description": "현재 패턴과 정확히 일치하는 과거 사례가 부족합니다."
            })
        
        return similar_patterns
    
    @staticmethod
    def _calculate_pattern_statistics(
        similar_patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        과거 패턴의 통계 계산
        
        Args:
            similar_patterns: 유사 패턴 리스트
            
        Returns:
            통계 정보
        """
        if not similar_patterns:
            return {}
        
        outcomes = [p["outcome"] for p in similar_patterns]
        outcome_percentages = [p["outcome_percentage"] for p in similar_patterns if p["outcome_percentage"] != 0]
        
        # 결과별 비율 계산
        uptrend_count = outcomes.count("uptrend")
        sideways_count = outcomes.count("sideways")
        downtrend_count = outcomes.count("downtrend")
        total = len(outcomes)
        
        return {
            "total_similar_patterns": total,
            "uptrend_ratio": f"{(uptrend_count / total * 100):.1f}%",
            "uptrend_count": uptrend_count,
            "sideways_ratio": f"{(sideways_count / total * 100):.1f}%",
            "sideways_count": sideways_count,
            "downtrend_ratio": f"{(downtrend_count / total * 100):.1f}%",
            "downtrend_count": downtrend_count,
            "average_outcome_percentage": f"{(sum(outcome_percentages) / len(outcome_percentages) if outcome_percentages else 0):.2f}%",
            "max_gain": f"{max(outcome_percentages):.2f}%" if outcome_percentages else "0%",
            "max_loss": f"{min(outcome_percentages):.2f}%" if outcome_percentages else "0%",
            "average_duration_days": f"{sum(p['duration_days'] for p in similar_patterns) / total:.1f}",
            "beginner_interpretation": PatternHistoryAnalysisService._get_statistic_interpretation(
                uptrend_count, sideways_count, downtrend_count, total
            )
        }
    
    @staticmethod
    def _get_outcome_description(outcome: str, percentage: float) -> str:
        """결과에 대한 설명"""
        if outcome == "uptrend":
            if percentage > 20:
                return f"강한 상승 ({percentage:+.1f}%)"
            elif percentage > 10:
                return f"중간 상승 ({percentage:+.1f}%)"
            else:
                return f"약한 상승 ({percentage:+.1f}%)"
        elif outcome == "downtrend":
            if percentage < -20:
                return f"강한 하락 ({percentage:+.1f}%)"
            elif percentage < -10:
                return f"중간 하락 ({percentage:+.1f}%)"
            else:
                return f"약한 하락 ({percentage:+.1f}%)"
        else:
            return f"횡보 ({percentage:+.1f}%)"
    
    @staticmethod
    def _get_statistic_interpretation(
        uptrend: int,
        sideways: int,
        downtrend: int,
        total: int
    ) -> str:
        """통계에 대한 초보자 친화형 해석"""
        if uptrend > total / 2:
            return "과거 유사 패턴에서는 상승하는 경우가 더 많았습니다. (참고용 정보)"
        elif downtrend > total / 2:
            return "과거 유사 패턴에서는 하락하는 경우가 더 많았습니다. (참고용 정보)"
        elif uptrend > downtrend:
            return "과거 유사 패턴에서는 상승하는 경향이 있었습니다. (참고용 정보)"
        elif downtrend > uptrend:
            return "과거 유사 패턴에서는 하락하는 경향이 있었습니다. (참고용 정보)"
        else:
            return "과거 유사 패턴의 결과가 다양했습니다. (참고용 정보)"
    
    @staticmethod
    def generate_pattern_comparison_summary(
        analysis_result: Dict[str, Any]
    ) -> str:
        """
        패턴 비교 요약 생성
        
        Args:
            analysis_result: 패턴 분석 결과
            
        Returns:
            요약 문구
        """
        similar_count = analysis_result.get("similar_patterns_count", 0)
        
        if similar_count == 0:
            return "현재 패턴과 정확히 일치하는 과거 사례가 없습니다. 따라서 과거 데이터 기반의 예측은 어렵습니다."
        
        stats = analysis_result.get("historical_statistics", {})
        uptrend_ratio = stats.get("uptrend_ratio", "0%")
        
        summary = f"과거 {similar_count}번의 유사한 패턴 중 "
        summary += f"{uptrend_ratio}가 상승했습니다. "
        summary += "다만, 과거 패턴이 반복된다는 보장은 없으며 참고용 정보일 뿐입니다."
        
        return summary


# 싱글톤 인스턴스
pattern_history_analyzer = PatternHistoryAnalysisService()
