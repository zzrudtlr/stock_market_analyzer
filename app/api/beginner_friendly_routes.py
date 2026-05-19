"""
초보자 친화형 분석 API 라우트
용어 설명, AI 질문, 초보자 설명 등
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

from app.services.term_dictionary_service import term_dictionary
from app.services.beginner_ai_explainer_service import beginner_explainer
from app.services.pros_cons_analysis_service import pros_cons_analyzer
from app.services.investment_style_analysis_service import investment_style_analyzer
from app.services.score_visualization_service import score_visualizer
from app.services.simple_market_summary_service import market_summary_service
from app.services.pattern_history_analysis_service import pattern_history_analyzer
from app.services.one_line_summary_service import one_line_summarizer
from app.services.ai_question_answer_service import ai_qa_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/beginner", tags=["beginner_friendly"])


# ==================== 1단계: 용어 설명 API ====================

@router.get("/terms")
async def get_all_terms():
    """모든 주식 용어 목록 조회"""
    terms = term_dictionary.get_all_terms()
    return {
        "success": True,
        "total_terms": len(terms),
        "terms": terms,
        "description": "주식 초보자를 위한 주식 용어 전체 목록입니다"
    }


@router.get("/terms/{term_name}")
async def get_term_explanation(term_name: str):
    """특정 용어의 설명 조회"""
    explanation = term_dictionary.get_term_explanation(term_name)
    
    if not explanation:
        raise HTTPException(status_code=404, detail=f"'{term_name}' 용어를 찾을 수 없습니다")
    
    related_terms = term_dictionary.get_related_terms(term_name)
    
    return {
        "success": True,
        "term": explanation.term_name,
        "short_explanation": explanation.short_explanation,
        "detailed_explanation": explanation.detailed_explanation,
        "category": explanation.category,
        "example": explanation.example,
        "related_terms": related_terms
    }


@router.get("/terms-by-category/{category}")
async def get_terms_by_category(category: str):
    """카테고리별 용어 조회"""
    terms = term_dictionary.search_terms_by_category(category)
    
    if not terms:
        raise HTTPException(status_code=404, detail=f"'{category}' 카테고리에 해당하는 용어가 없습니다")
    
    return {
        "success": True,
        "category": category,
        "term_count": len(terms),
        "terms": [
            {
                "name": term.term_name,
                "short_explanation": term.short_explanation
            }
            for term in terms
        ]
    }


# ==================== 2단계: 초보자 설명 변환 API ====================

@router.post("/stock/{stock_code}/beginner-summary")
async def get_beginner_summary(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    주식 분석 데이터를 초보자 친화형으로 변환
    
    분석 데이터 예시:
    {
        "current_price": 50000,
        "rsi": 65,
        "ma5": 49000,
        "ma20": 48000,
        "ma60": 47000,
        "volume_change_rate": 120,
        "foreign_net": 1500000,
        "institution_net": 500000,
        "news_sentiment": "positive",
        "theme_strength": "strong",
        "volatility_level": "normal"
    }
    """
    try:
        summary = beginner_explainer.generate_beginner_summary(
            stock_code=stock_code,
            stock_name=analysis_data.get("stock_name", stock_code),
            analysis_data=analysis_data
        )
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        logger.error(f"초보자 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="초보자 요약 생성 실패")


# ==================== 3단계: 긍정/위험 요소 분석 API ====================

@router.post("/stock/{stock_code}/pros-cons")
async def analyze_pros_and_cons(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    종목의 긍정 요소와 위험 요소 분석
    """
    try:
        result = pros_cons_analyzer.analyze_pros_and_cons(analysis_data)
        
        return {
            "success": True,
            "stock_code": stock_code,
            "data": result
        }
    except Exception as e:
        logger.error(f"긍정/위험 요소 분석 실패: {e}")
        raise HTTPException(status_code=500, detail="분석 실패")


# ==================== 4단계: 투자 스타일 분석 API ====================

@router.post("/stock/{stock_code}/investment-style")
async def analyze_investment_style(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    종목의 투자 스타일 분석 및 분류
    """
    try:
        result = investment_style_analyzer.analyze_investment_style(analysis_data)
        
        return {
            "success": True,
            "stock_code": stock_code,
            "data": result
        }
    except Exception as e:
        logger.error(f"투자 스타일 분석 실패: {e}")
        raise HTTPException(status_code=500, detail="분석 실패")


# ==================== 5단계: 점수 시각화 API ====================

@router.post("/stock/{stock_code}/visualization")
async def get_score_visualization(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    여러 지표의 시각화 게이지 생성
    """
    try:
        gauges = score_visualizer.create_multiple_gauges(analysis_data)
        
        gauge_data = {}
        for key, gauge in gauges.items():
            gauge_data[key] = {
                "label": gauge.label,
                "value": gauge.value,
                "gauge_bars": gauge.gauge_bars,
                "percentage": gauge.percentage,
                "level": gauge.level.value,
                "description": gauge.description,
                "emoji": gauge.emoji,
                "beginner_comment": gauge.beginner_comment
            }
        
        return {
            "success": True,
            "stock_code": stock_code,
            "gauges": gauge_data,
            "visual_summary": score_visualizer.create_visual_summary(gauges)
        }
    except Exception as e:
        logger.error(f"시각화 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="시각화 생성 실패")


# ==================== 6단계: 시장 흐름 요약 API ====================

@router.post("/market/simple-summary")
async def get_market_summary(
    market_data: Dict[str, Any]
):
    """
    현재 시장 전체 상태를 한줄로 요약
    """
    try:
        summary = market_summary_service.generate_simple_market_summary(market_data)
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        logger.error(f"시장 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="시장 요약 생성 실패")


@router.post("/market/hot-themes")
async def get_hot_themes(
    market_data: Dict[str, Any]
):
    """오늘 강한 테마"""
    try:
        themes = market_summary_service.generate_today_hot_themes(market_data)
        return {
            "success": True,
            "data": themes
        }
    except Exception as e:
        logger.error(f"핫 테마 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="조회 실패")


@router.post("/market/weak-themes")
async def get_weak_themes(
    market_data: Dict[str, Any]
):
    """오늘 약한 테마"""
    try:
        themes = market_summary_service.generate_today_weak_themes(market_data)
        return {
            "success": True,
            "data": themes
        }
    except Exception as e:
        logger.error(f"약한 테마 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="조회 실패")


# ==================== 7단계: 과거 패턴 분석 API ====================

@router.post("/stock/{stock_code}/pattern-history")
async def analyze_pattern_history(
    stock_code: str,
    pattern_data: Dict[str, Any]
):
    """
    현재 패턴과 과거 유사 패턴 비교
    """
    try:
        result = pattern_history_analyzer.analyze_similar_patterns(stock_code, pattern_data)
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"패턴 분석 실패: {e}")
        raise HTTPException(status_code=500, detail="패턴 분석 실패")


# ==================== 8단계: 종목 한줄 요약 API ====================

@router.post("/stock/{stock_code}/one-line-summary")
async def get_one_line_summary(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    종목을 한 줄로 요약
    """
    try:
        summary = one_line_summarizer.generate_one_line_summary(
            stock_code=stock_code,
            stock_name=analysis_data.get("stock_name", stock_code),
            analysis_data=analysis_data
        )
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        logger.error(f"한줄 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="생성 실패")


@router.post("/stock/{stock_code}/beginner-one-line")
async def get_beginner_one_line(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    초보자 친화형 종목 한줄 요약
    """
    try:
        summary = one_line_summarizer.generate_beginner_friendly_summary(
            stock_code=stock_code,
            stock_name=analysis_data.get("stock_name", stock_code),
            analysis_data=analysis_data
        )
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        logger.error(f"초보자 한줄 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="생성 실패")


# ==================== 9단계: AI 질문 기능 API ====================

@router.post("/stock/{stock_code}/ask")
async def ask_question(
    stock_code: str,
    question: str = Query(..., description="사용자 질문"),
    stock_name: Optional[str] = None,
    analysis_data: Optional[Dict[str, Any]] = None
):
    """
    AI 질문 기능
    현재 분석 데이터를 기반으로 사용자 질문에 답변
    
    예시 질문:
    - "왜 위험한가요?"
    - "왜 강세인가요?"
    - "RSI가 뭔가요?"
    - "지금 사야 하나요?"
    """
    try:
        if analysis_data is None:
            analysis_data = {}
        
        result = ai_qa_service.answer_question(
            question=question,
            stock_code=stock_code,
            stock_name=stock_name or stock_code,
            analysis_data=analysis_data
        )
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"질문 답변 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="답변 생성 실패")


@router.get("/stock/{stock_code}/questions")
async def get_example_questions(stock_code: str):
    """해당 종목에 대해 자주 묻는 질문 목록"""
    example_questions = [
        "왜 위험한가요?",
        "왜 강세인가요?",
        "현재 과열 상태인가요?",
        "시장 분위기는 어떤가요?",
        "외국인 순매수가 뭔가요?",
        "거래량이 왜 중요한가요?",
        "지금 사야 하나요?",
        "앞으로 어떻게 될까요?"
    ]
    
    return {
        "success": True,
        "stock_code": stock_code,
        "example_questions": example_questions,
        "tip": "위 질문들을 /ask 엔드포인트의 question 파라미터로 사용할 수 있습니다"
    }


# ==================== 종합 대시보드 API ====================

@router.post("/stock/{stock_code}/complete-beginner-analysis")
async def get_complete_beginner_analysis(
    stock_code: str,
    analysis_data: Dict[str, Any]
):
    """
    초보자를 위한 종합 분석 대시보드
    모든 초보자 친화형 분석을 한 번에 조회
    """
    try:
        stock_name = analysis_data.get("stock_name", stock_code)
        
        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "analyses": {}
        }
        
        # 1. 한줄 요약
        result["analyses"]["one_line_summary"] = one_line_summarizer.generate_one_line_summary(
            stock_code, stock_name, analysis_data
        )
        
        # 2. 긍정/위험 요소
        result["analyses"]["pros_cons"] = pros_cons_analyzer.analyze_pros_and_cons(analysis_data)
        
        # 3. 투자 스타일
        result["analyses"]["investment_style"] = investment_style_analyzer.analyze_investment_style(analysis_data)
        
        # 4. 시각화 게이지
        gauges = score_visualizer.create_multiple_gauges(analysis_data)
        result["analyses"]["visualizations"] = {
            key: {
                "label": g.label,
                "percentage": g.percentage,
                "gauge_bars": g.gauge_bars,
                "description": g.description,
                "comment": g.beginner_comment
            }
            for key, g in gauges.items()
        }
        
        # 5. 초보자 설명
        result["analyses"]["beginner_summary"] = beginner_explainer.generate_beginner_summary(
            stock_code, stock_name, analysis_data
        )
        
        # 6. 패턴 분석
        current_pattern = {
            "volume_surge": analysis_data.get("volume_change_rate", 0) > 100,
            "ma_crossover": False,
            "rsi_overbought": analysis_data.get("rsi", 50) > 75,
            "strong_theme": analysis_data.get("theme_strength", "weak") == "strong",
            "foreign_buying": analysis_data.get("foreign_net", 0) > 0,
            "price_change": 0
        }
        result["analyses"]["pattern_history"] = pattern_history_analyzer.analyze_similar_patterns(
            stock_code, current_pattern
        )
        
        result["success"] = True
        return result
        
    except Exception as e:
        logger.error(f"종합 분석 생성 실패: {e}")
        raise HTTPException(status_code=500, detail="분석 생성 실패")


# ==================== 안내 및 도움말 ====================

@router.get("/guide")
async def get_beginner_guide():
    """초보자 가이드"""
    return {
        "success": True,
        "title": "주식 초보자 투자 분석 가이드",
        "disclaimer": "본 서비스는 참고용 분석입니다. 투자 판단은 사용자 본인 책임입니다.",
        "features": [
            {
                "name": "용어 설명",
                "description": "RSI, MA, 거래량 등 주식 용어에 대한 설명",
                "endpoint": "/beginner/terms/{term_name}"
            },
            {
                "name": "한줄 요약",
                "description": "종목을 한 문장으로 설명",
                "endpoint": "/beginner/stock/{stock_code}/one-line-summary"
            },
            {
                "name": "긍정/위험 요소",
                "description": "좋은 점과 위험한 점을 분리해서 표시",
                "endpoint": "/beginner/stock/{stock_code}/pros-cons"
            },
            {
                "name": "투자 스타일",
                "description": "종목의 특성을 초보자가 이해하기 쉽게 분류",
                "endpoint": "/beginner/stock/{stock_code}/investment-style"
            },
            {
                "name": "시각화",
                "description": "게이지로 시각적으로 이해할 수 있는 지표",
                "endpoint": "/beginner/stock/{stock_code}/visualization"
            },
            {
                "name": "AI 질문",
                "description": "현재 분석을 기반으로 질문에 답변",
                "endpoint": "/beginner/stock/{stock_code}/ask?question=..."
            },
            {
                "name": "종합 분석",
                "description": "모든 분석을 한 번에 조회",
                "endpoint": "/beginner/stock/{stock_code}/complete-beginner-analysis"
            }
        ],
        "example_queries": [
            "용어 설명: /beginner/terms/RSI",
            "종합 분석: /beginner/stock/005930/complete-beginner-analysis",
            "AI 질문: /beginner/stock/005930/ask?question=왜 위험한가요?"
        ]
    }
