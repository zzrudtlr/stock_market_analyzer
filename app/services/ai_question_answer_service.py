"""
AI 질문 기능
사용자 질문에 현재 분석 데이터를 기반으로 답변 제공
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class AIQuestionAnswerService:
    """AI 질문 답변 서비스"""
    
    DISCLAIMER = "본 답변은 현재 분석 데이터를 기반으로 생성된 참고용입니다. 투자 판단은 사용자 본인 책임입니다."
    
    # 질문 템플릿 정의
    QUESTION_TEMPLATES = {
        "why_risky": {
            "patterns": ["왜 위험", "위험", "손실", "하락"],
            "response_key": "risk_explanation"
        },
        "why_strong": {
            "patterns": ["왜 강세", "왜 올라", "상승", "긍정"],
            "response_key": "strength_explanation"
        },
        "what_is_term": {
            "patterns": ["뭔가요", "뭐예요", "뜻", "의미", "뭐", "무엇"],
            "response_key": "term_explanation"
        },
        "why_important": {
            "patterns": ["왜 중요", "의미가", "영향", "중요"],
            "response_key": "importance_explanation"
        },
        "is_overbought": {
            "patterns": ["과열", "오버", "지나치", "과도"],
            "response_key": "overbought_explanation"
        },
        "buy_now": {
            "patterns": ["지금", "사야", "사자", "매수"],
            "response_key": "buy_caution"
        },
        "market_condition": {
            "patterns": ["시장", "상태", "분위기", "분위"],
            "response_key": "market_explanation"
        },
        "future_outlook": {
            "patterns": ["앞으로", "앞", "미래", "어떻게"],
            "response_key": "future_caution"
        }
    }
    
    @staticmethod
    def answer_question(
        question: str,
        stock_code: str,
        stock_name: str,
        analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        사용자 질문에 답변 생성
        
        Args:
            question: 사용자 질문
            stock_code: 종목 코드
            stock_name: 종목명
            analysis_data: 분석 데이터
            
        Returns:
            답변 정보
        """
        result = {
            "question": question,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "answer": "",
            "question_type": "",
            "confidence": 0,
            "related_factors": [],
            "generated_at": datetime.now().isoformat(),
            "disclaimer": AIQuestionAnswerService.DISCLAIMER
        }
        
        # 질문 유형 분류
        question_type = AIQuestionAnswerService._classify_question(question)
        result["question_type"] = question_type
        
        # 질문 유형에 따른 답변 생성
        if question_type == "why_risky":
            answer, factors, confidence = AIQuestionAnswerService._answer_why_risky(
                analysis_data, stock_name
            )
        elif question_type == "why_strong":
            answer, factors, confidence = AIQuestionAnswerService._answer_why_strong(
                analysis_data, stock_name
            )
        elif question_type == "what_is_term":
            answer, factors, confidence = AIQuestionAnswerService._answer_term_question(
                question, stock_name
            )
        elif question_type == "why_important":
            answer, factors, confidence = AIQuestionAnswerService._answer_importance(
                question, analysis_data, stock_name
            )
        elif question_type == "is_overbought":
            answer, factors, confidence = AIQuestionAnswerService._answer_overbought(
                analysis_data, stock_name
            )
        elif question_type == "buy_now":
            answer, factors, confidence = AIQuestionAnswerService._answer_buy_caution(
                question, stock_name
            )
        elif question_type == "market_condition":
            answer, factors, confidence = AIQuestionAnswerService._answer_market_condition(
                analysis_data, stock_name
            )
        elif question_type == "future_outlook":
            answer, factors, confidence = AIQuestionAnswerService._answer_future_caution(
                stock_name
            )
        else:
            answer, factors, confidence = AIQuestionAnswerService._answer_general(
                question, stock_name, analysis_data
            )
        
        result["answer"] = answer
        result["related_factors"] = factors
        result["confidence"] = confidence
        
        return result
    
    @staticmethod
    def _classify_question(question: str) -> str:
        """
        질문 유형 분류
        
        Args:
            question: 질문 문자열
            
        Returns:
            질문 유형
        """
        question_lower = question.lower()
        
        for q_type, template in AIQuestionAnswerService.QUESTION_TEMPLATES.items():
            for pattern in template["patterns"]:
                if pattern in question_lower:
                    return q_type
        
        return "general"
    
    @staticmethod
    def _answer_why_risky(analysis_data: Dict[str, Any], stock_name: str) -> Tuple[str, List[str], int]:
        """위험 이유 설명"""
        risk_factors = []
        
        rsi = analysis_data.get("rsi", 50)
        volatility = analysis_data.get("volatility_level", "normal")
        foreign_net = analysis_data.get("foreign_net", 0)
        theme_strength = analysis_data.get("theme_strength", "weak")
        
        if rsi > 75:
            risk_factors.append("현재 주가가 단기적으로 과도하게 올라있는 상태입니다")
        
        if volatility == "high":
            risk_factors.append("주가 등락폭이 크므로 손실 가능성도 큽니다")
        
        if foreign_net < 0:
            risk_factors.append("외국인 투자자들이 팔고 있어서 기술적 약세입니다")
        
        if theme_strength == "weak":
            risk_factors.append("속한 테마가 약해지면서 부정적 영향을 받을 수 있습니다")
        
        if not risk_factors:
            risk_factors.append("특별한 위험 신호는 보이지 않습니다")
        
        answer = f"{stock_name}이 위험하게 보이는 이유:\n\n"
        answer += "\n".join(f"- {factor}" for factor in risk_factors)
        answer += "\n\n⚠️ 다만, 위험도 과거 패턴과 현재 시장 상황에 따라 달라질 수 있습니다."
        
        confidence = min(90, 60 + len(risk_factors) * 10)
        
        return answer, risk_factors, confidence
    
    @staticmethod
    def _answer_why_strong(analysis_data: Dict[str, Any], stock_name: str) -> Tuple[str, List[str], int]:
        """강세 이유 설명"""
        strength_factors = []
        
        foreign_net = analysis_data.get("foreign_net", 0)
        institution_net = analysis_data.get("institution_net", 0)
        volume_change = analysis_data.get("volume_change_rate", 0)
        theme_strength = analysis_data.get("theme_strength", "weak")
        current_price = analysis_data.get("current_price", 0)
        ma5 = analysis_data.get("ma5", 0)
        ma20 = analysis_data.get("ma20", 0)
        ma60 = analysis_data.get("ma60", 0)
        
        if foreign_net > 0:
            strength_factors.append("외국인 투자자들이 매수하고 있습니다")
        
        if institution_net > 0:
            strength_factors.append("국내 기관투자자들이 매수하는 중입니다")
        
        if volume_change > 100:
            strength_factors.append(f"거래량이 {volume_change:.0f}% 증가해 시장 관심도가 높습니다")
        
        if theme_strength == "strong":
            strength_factors.append("속한 테마가 시장에서 강세를 보이고 있습니다")
        
        if current_price > 0 and ma5 > 0 and ma20 > 0 and ma60 > 0:
            if current_price > ma5 > ma20 > ma60:
                strength_factors.append("단기부터 장기까지 모두 상승 추세를 보이고 있습니다")
            elif current_price > ma20:
                strength_factors.append("중기 상승 흐름이 형성되어 있습니다")
        
        if not strength_factors:
            strength_factors.append("특별한 강세 신호는 보이지 않습니다")
        
        answer = f"{stock_name}이 강세로 보이는 이유:\n\n"
        answer += "\n".join(f"- {factor}" for factor in strength_factors)
        answer += "\n\n📈 다만, 강세도 시장 상황 변화에 따라 언제든 바뀔 수 있습니다."
        
        confidence = min(90, 60 + len(strength_factors) * 10)
        
        return answer, strength_factors, confidence
    
    @staticmethod
    def _answer_term_question(question: str, stock_name: str) -> Tuple[str, List[str], int]:
        """용어 설명"""
        from app.services.term_dictionary_service import term_dictionary
        
        # 질문에서 용어 추출
        terms = ["RSI", "MA5", "MA20", "MA60", "거래량", "외국인", "기관", "PER", "PBR", "ROE", "변동성", "골든크로스", "데드크로스"]
        found_term = None
        
        for term in terms:
            if term.lower() in question.lower():
                found_term = term
                break
        
        if found_term:
            explanation = term_dictionary.get_term_explanation(found_term)
            if explanation:
                answer = f"'{found_term}'에 대한 설명:\n\n"
                answer += f"📚 간단 설명: {explanation.short_explanation}\n\n"
                answer += f"📖 상세 설명:\n{explanation.detailed_explanation}"
                return answer, [found_term], 90
        
        answer = f"죄송하지만, 질문에서 구체적인 용어를 찾을 수 없습니다. RSI, MA, 거래량, 수급, 실적 지표 등의 용어에 대해 알려드릴 수 있습니다."
        return answer, [], 30
    
    @staticmethod
    def _answer_importance(question: str, analysis_data: Dict[str, Any], stock_name: str) -> Tuple[str, List[str], int]:
        """중요성 설명"""
        importance_factors = []
        
        # 거래량이 언급되면
        if "거래량" in question:
            importance_factors.append("가격 변동의 신뢰성을 판단")
            importance_factors.append("추세 변화의 신호")
            answer = f"{stock_name}의 거래량이 중요한 이유:\n\n"
        # 수급이 언급되면
        elif "수급" in question or "외국인" in question or "기관" in question:
            importance_factors.append("큰 자금의 방향을 파악")
            importance_factors.append("시장의 진정한 수요/공급 파악")
            answer = f"{stock_name}의 수급이 중요한 이유:\n\n"
        # 추세가 언급되면
        elif "추세" in question or "이동평균" in question:
            importance_factors.append("주가의 방향성 파악")
            importance_factors.append("투자 타이밍 결정")
            answer = f"{stock_name}의 추세가 중요한 이유:\n\n"
        else:
            importance_factors.append("현재 시장 상태 파악")
            importance_factors.append("투자 결정의 근거 제공")
            answer = f"{stock_name}의 분석이 중요한 이유:\n\n"
        
        answer += "\n".join(f"- {factor}" for factor in importance_factors)
        answer += "\n\n💡 분석 정보는 참고용이며, 최종 투자 결정은 본인의 판단입니다."
        
        return answer, importance_factors, 75
    
    @staticmethod
    def _answer_overbought(analysis_data: Dict[str, Any], stock_name: str) -> Tuple[str, List[str], int]:
        """과열 상태 설명"""
        rsi = analysis_data.get("rsi", 50)
        volatility = analysis_data.get("volatility_level", "normal")
        
        factors = []
        
        if rsi > 75:
            factors.append(f"RSI가 {rsi:.0f}로 75 이상입니다. 단기 과열 상태입니다.")
        elif rsi > 70:
            factors.append(f"RSI가 {rsi:.0f}로 높은 편입니다. 과열 초기 단계입니다.")
        else:
            factors.append(f"RSI가 {rsi:.0f}로 과열 상태는 아닙니다.")
        
        if volatility == "high":
            factors.append("높은 변동성으로 인해 급락 가능성이 있습니다.")
        
        answer = f"{stock_name}의 현재 상태:\n\n"
        answer += "\n".join(f"- {factor}" for factor in factors)
        answer += "\n\n⚠️ 과열 상태에서는 급락할 수 있으므로 주의가 필요합니다. 하지만 과열이 반드시 하락을 의미하지는 않습니다."
        
        return answer, factors, 80
    
    @staticmethod
    def _answer_buy_caution(question: str, stock_name: str) -> Tuple[str, List[str], int]:
        """매수 주의 및 책임 고지"""
        factors = ["투자 판단은 본인의 책임입니다", "과거 수익률은 미래를 보장하지 않습니다"]
        
        answer = f"'{stock_name}' 매수에 대해:\n\n"
        answer += "⚠️ 투자 권유 또는 추천이 불가능합니다.\n\n"
        answer += "본 서비스는 분석 정보만 제공하며, 투자 결정은 전적으로 본인의 책임입니다.\n"
        answer += "- 충분한 조사 후 결정하세요\n"
        answer += "- 손절 계획을 미리 세우세요\n"
        answer += "- 잃을 수 있는 금액만 투자하세요\n"
        answer += "- 전문가 의견도 참고하세요\n\n"
        answer += "본 분석은 참고용입니다."
        
        return answer, factors, 100
    
    @staticmethod
    def _answer_market_condition(analysis_data: Dict[str, Any], stock_name: str) -> Tuple[str, List[str], int]:
        """시장 상태 설명"""
        volatility = analysis_data.get("volatility_level", "normal")
        theme_strength = analysis_data.get("theme_strength", "weak")
        foreign_net = analysis_data.get("foreign_net", 0)
        
        factors = []
        
        if volatility == "high":
            factors.append("변동성이 높아 시장이 불안정합니다")
        elif volatility == "low":
            factors.append("변동성이 낮아 시장이 안정적입니다")
        else:
            factors.append("변동성이 정상 수준입니다")
        
        if theme_strength == "strong":
            factors.append("특정 테마 중심으로 자금이 쏠려 있습니다")
        else:
            factors.append("주도 테마가 명확하지 않습니다")
        
        if foreign_net > 0:
            factors.append("외국인 자금이 들어오는 상황입니다")
        elif foreign_net < 0:
            factors.append("외국인 자금이 빠져나가는 상황입니다")
        
        answer = f"현재 시장 상태:\n\n"
        answer += "\n".join(f"- {factor}" for factor in factors)
        answer += f"\n\n📊 {stock_name}도 이러한 시장 환경의 영향을 받고 있습니다."
        
        return answer, factors, 75
    
    @staticmethod
    def _answer_future_caution(stock_name: str) -> Tuple[str, List[str], int]:
        """미래 전망 주의"""
        factors = ["미래 예측은 불가능합니다"]
        
        answer = f"{stock_name}의 미래에 대해:\n\n"
        answer += "⚠️ 본 서비스는 미래 가격을 예측하지 않습니다.\n"
        answer += "과거 데이터와 현재 분석은 참고용일 뿐, 미래를 보장하지 않습니다.\n\n"
        answer += "시장은 예측 불가능한 변수들로 영향을 받습니다:\n"
        answer += "- 경제 지표 발표\n"
        answer += "- 정책 변화\n"
        answer += "- 기업 실적 발표\n"
        answer += "- 글로벌 이슈\n"
        answer += "- 심리적 요인\n\n"
        answer += "따라서 철저한 계획과 신중한 판단이 필수적입니다."
        
        return answer, factors, 100
    
    @staticmethod
    def _answer_general(question: str, stock_name: str, analysis_data: Dict[str, Any]) -> Tuple[str, List[str], int]:
        """일반 질문 답변"""
        factors = []
        
        answer = f"'{question}'에 대해:\n\n"
        answer += f"현재 {stock_name}의 분석 데이터를 기반으로 설명드리겠습니다.\n\n"
        
        # 현재 상태 요약
        rsi = analysis_data.get("rsi", 50)
        volume_change = analysis_data.get("volume_change_rate", 0)
        
        if rsi > 70:
            answer += "- 단기 강도가 높습니다\n"
            factors.append("높은 RSI")
        elif rsi < 30:
            answer += "- 단기 약도가 있습니다\n"
            factors.append("낮은 RSI")
        
        if volume_change > 50:
            answer += f"- 거래량이 증가했습니다 ({volume_change:.0f}%)\n"
            factors.append("거래량 증가")
        
        answer += "\n더 구체적인 질문이 있으시면 말씀해 주세요."
        
        return answer, factors, 50


# 싱글톤 인스턴스
ai_qa_service = AIQuestionAnswerService()
