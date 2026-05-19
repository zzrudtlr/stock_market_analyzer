"""
특정 날짜 시장 분석 서비스

사용자가 지정한 특정 날짜에 대해 시장 분석을 자동으로 수행합니다.
강세 예상 종목 TOP 5, 약세 예상 종목 TOP 5, 주의 종목을 정리하여
JSON 형식 분석 리포트를 생성합니다.

분석 기준:
  - 강세 예상 종목: bullish_score가 높은 종목 (긍정 신호 강한 순)
  - 약세 예상 종목: bearish_score가 높은 종목 (위험 신호 강한 순)
  - 주의 종목: 혼합 신호 (bullish_score와 bearish_score 모두 중간 이상)
  - 시장 종합 의견: 전체 종목의 신호 분포 분석

제약 조건:
  - 투자 추천, 매수/매도 권유 표현 금지
  - 참고용 분석만 제공
  - 각 종목당 분석 근거 3~5개 제시
  - 초보자도 이해하기 쉬운 설명 제공
"""
import json
import logging
from datetime import date
from typing import Dict, List, Any, Optional

from sqlalchemy import select, and_, text

from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.stock import Stock

logger = logging.getLogger(__name__)

DISCLAIMER = "본 분석은 과거 데이터 기반 참고용이며 투자 판단은 사용자 본인 책임입니다."

# 금지된 표현들 (투자 추천 방지)
_BANNED_WORDS = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
    "꼭 사세요", "큰 수익", "추천합니다",
]


class MarketDateAnalysisService:
    """특정 날짜 시장 분석 서비스"""

    @staticmethod
    def analyze_market_by_date(
        analysis_date: date,
        top_count: int = 5,
        include_mixed_signals: bool = True,
    ) -> Dict[str, Any]:
        """
        특정 날짜의 시장을 분석하고 강세/약세 종목을 정리합니다.

        Args:
            analysis_date: 분석 대상 날짜
            top_count: 상위 N개 종목 (기본값 5)
            include_mixed_signals: 혼합 신호 종목 포함 여부 (기본값 True)

        Returns:
            {
                "analysis_date": "2026-05-20",
                "bullish_stocks": [...],
                "bearish_stocks": [...],
                "mixed_signal_stocks": [...],
                "market_overview": {...},
                "analysis_summary": "...",
                "disclaimer": "..."
            }
        """
        session = get_db_session()
        try:
            # 1. 해당 날짜 분석 데이터 조회
            results = MarketDateAnalysisService._fetch_analysis_results(
                session, analysis_date
            )

            if not results:
                return {
                    "status": "no_data",
                    "analysis_date": str(analysis_date),
                    "message": f"{analysis_date} 날짜의 분석 데이터가 없습니다. 먼저 분석을 실행하세요.",
                    "disclaimer": DISCLAIMER,
                }

            # 2. 종목별 상세 분석 데이터 구성
            stocks_with_names = MarketDateAnalysisService._enrich_stock_data(
                session, results
            )

            # 3. 강세/약세/혼합 신호 종목 분류
            bullish = sorted(
                [s for s in stocks_with_names if s["bullish_score"] >= 70],
                key=lambda x: x["bullish_score"],
                reverse=True,
            )[:top_count]

            bearish = sorted(
                [s for s in stocks_with_names if s["bearish_score"] >= 70],
                key=lambda x: x["bearish_score"],
                reverse=True,
            )[:top_count]

            mixed = sorted(
                [
                    s
                    for s in stocks_with_names
                    if (50 <= s["bullish_score"] < 70)
                    and (50 <= s["bearish_score"] < 70)
                ],
                key=lambda x: abs(x["bullish_score"] - x["bearish_score"]),
            )[:top_count]

            # 4. 각 종목별 분석 근거 생성
            bullish_analyzed = [
                MarketDateAnalysisService._generate_stock_analysis(s, "bullish")
                for s in bullish
            ]
            bearish_analyzed = [
                MarketDateAnalysisService._generate_stock_analysis(s, "bearish")
                for s in bearish
            ]
            mixed_analyzed = [
                MarketDateAnalysisService._generate_stock_analysis(s, "mixed")
                for s in mixed
            ]

            # 5. 시장 종합 의견 생성
            market_overview = MarketDateAnalysisService._generate_market_overview(
                stocks_with_names, analysis_date
            )

            # 6. 분석 요약 생성
            analysis_summary = MarketDateAnalysisService._generate_summary(
                bullish_analyzed, bearish_analyzed, market_overview
            )

            return {
                "status": "success",
                "analysis_date": str(analysis_date),
                "bullish_stocks": bullish_analyzed,
                "bearish_stocks": bearish_analyzed,
                "mixed_signal_stocks": mixed_analyzed if include_mixed_signals else [],
                "market_overview": market_overview,
                "analysis_summary": analysis_summary,
                "disclaimer": DISCLAIMER,
            }

        except Exception as e:
            logger.error(f"시장 분석 중 오류: {e}", exc_info=True)
            return {
                "status": "error",
                "analysis_date": str(analysis_date),
                "error": str(e),
                "disclaimer": DISCLAIMER,
            }
        finally:
            session.close()

    @staticmethod
    def _fetch_analysis_results(
        session, analysis_date: date
    ) -> List[StockAnalysisResult]:
        """해당 날짜의 분석 결과 조회"""
        query = select(StockAnalysisResult).where(
            StockAnalysisResult.analysis_date == analysis_date
        )
        return session.execute(query).scalars().all()

    @staticmethod
    def _enrich_stock_data(
        session, results: List[StockAnalysisResult]
    ) -> List[Dict[str, Any]]:
        """분석 결과에 종목 정보를 추가"""
        stock_codes = [r.stock_code for r in results]
        
        # 종목 정보 조회
        query = select(Stock).where(Stock.stock_code.in_(stock_codes))
        stocks_dict = {s.stock_code: s for s in session.execute(query).scalars()}

        enriched = []
        for result in results:
            stock = stocks_dict.get(result.stock_code)
            enriched.append(
                {
                    "stock_code": result.stock_code,
                    "stock_name": stock.stock_name if stock else "N/A",
                    "market": stock.market if stock else "N/A",
                    "sector": stock.sector if stock else "N/A",
                    "daily_return": float(result.daily_return) if result.daily_return else 0,
                    "return_5d": float(result.return_5d) if result.return_5d else 0,
                    "return_20d": float(result.return_20d) if result.return_20d else 0,
                    "return_60d": float(result.return_60d) if result.return_60d else 0,
                    "rsi14": float(result.rsi14) if result.rsi14 else 0,
                    "volume_ratio_5d": float(result.volume_ratio_5d)
                    if result.volume_ratio_5d
                    else 1.0,
                    "volume_ratio_20d": float(result.volume_ratio_20d)
                    if result.volume_ratio_20d
                    else 1.0,
                    "momentum_score": float(result.momentum_score) if result.momentum_score else 0,
                    "trend_score": float(result.trend_score) if result.trend_score else 0,
                    "volume_score": float(result.volume_score) if result.volume_score else 0,
                    "risk_score": float(result.risk_score) if result.risk_score else 0,
                    "bullish_score": float(result.bullish_score) if result.bullish_score else 0,
                    "bearish_score": float(result.bearish_score) if result.bearish_score else 0,
                    "final_signal": result.final_signal or "관망",
                }
            )

        return enriched

    @staticmethod
    def _generate_stock_analysis(
        stock_data: Dict[str, Any], analysis_type: str
    ) -> Dict[str, Any]:
        """
        개별 종목 분석 생성 (강세/약세/혼합)
        
        Args:
            stock_data: 종목 데이터
            analysis_type: "bullish", "bearish", "mixed"
        """
        reasoning = []

        if analysis_type == "bullish":
            # 강세 분석 근거
            if stock_data["daily_return"] > 2:
                reasoning.append(
                    f"당일 {stock_data['daily_return']:.2f}% 상승으로 강한 매수 심리"
                )
            
            if stock_data["return_5d"] > 5:
                reasoning.append(
                    f"최근 5일 {stock_data['return_5d']:.2f}% 상승으로 상승 추세 형성"
                )
            
            if stock_data["rsi14"] > 70:
                reasoning.append(f"RSI14가 {stock_data['rsi14']:.1f}로 높은 모멘텀 유지")
            
            if stock_data["volume_ratio_5d"] > 1.5:
                reasoning.append(f"거래량이 평소의 {stock_data['volume_ratio_5d']:.1f}배로 증가")
            
            if stock_data["momentum_score"] > 70:
                reasoning.append("모멘텀 지표가 강한 상승 신호 발생")

            return {
                "stock_code": stock_data["stock_code"],
                "stock_name": stock_data["stock_name"],
                "market": stock_data["market"],
                "sector": stock_data["sector"],
                "analysis_type": "강세 예상",
                "bullish_score": round(stock_data["bullish_score"], 1),
                "key_metrics": {
                    "daily_return": round(stock_data["daily_return"], 2),
                    "return_5d": round(stock_data["return_5d"], 2),
                    "return_20d": round(stock_data["return_20d"], 2),
                    "rsi14": round(stock_data["rsi14"], 1),
                    "volume_ratio_5d": round(stock_data["volume_ratio_5d"], 2),
                },
                "reasoning": reasoning[:5] if reasoning else ["긍정 신호 탐지"],
                "note": "강한 상승 신호를 보이고 있습니다",
            }

        elif analysis_type == "bearish":
            # 약세 분석 근거
            if stock_data["daily_return"] < -2:
                reasoning.append(
                    f"당일 {abs(stock_data['daily_return']):.2f}% 하락으로 약한 심리"
                )
            
            if stock_data["return_5d"] < -5:
                reasoning.append(
                    f"최근 5일 {abs(stock_data['return_5d']):.2f}% 하락으로 하락 추세"
                )
            
            if stock_data["rsi14"] < 30:
                reasoning.append(f"RSI14가 {stock_data['rsi14']:.1f}로 약한 모멘텀")
            
            if stock_data["risk_score"] > 70:
                reasoning.append("위험 신호가 강하게 나타나고 있습니다")
            
            if stock_data["bearish_score"] > 80:
                reasoning.append("약세 지표가 복합적으로 발생 중")

            return {
                "stock_code": stock_data["stock_code"],
                "stock_name": stock_data["stock_name"],
                "market": stock_data["market"],
                "sector": stock_data["sector"],
                "analysis_type": "약세 주의",
                "bearish_score": round(stock_data["bearish_score"], 1),
                "key_metrics": {
                    "daily_return": round(stock_data["daily_return"], 2),
                    "return_5d": round(stock_data["return_5d"], 2),
                    "return_20d": round(stock_data["return_20d"], 2),
                    "rsi14": round(stock_data["rsi14"], 1),
                    "volume_ratio_5d": round(stock_data["volume_ratio_5d"], 2),
                },
                "reasoning": reasoning[:5] if reasoning else ["부정 신호 탐지"],
                "risk_warning": "약세 신호가 나타나고 있으니 주의가 필요합니다",
            }

        else:  # mixed
            bullish_reasons = []
            bearish_reasons = []

            if stock_data["daily_return"] > 1:
                bullish_reasons.append(f"당일 {stock_data['daily_return']:.2f}% 상승")
            elif stock_data["daily_return"] < -1:
                bearish_reasons.append(f"당일 {abs(stock_data['daily_return']):.2f}% 하락")

            if stock_data["return_5d"] > 3:
                bullish_reasons.append(f"5일 {stock_data['return_5d']:.2f}% 상승")
            elif stock_data["return_5d"] < -3:
                bearish_reasons.append(f"5일 {abs(stock_data['return_5d']):.2f}% 하락")

            if stock_data["rsi14"] > 60:
                bullish_reasons.append(f"RSI 높음 ({stock_data['rsi14']:.1f})")
            elif stock_data["rsi14"] < 40:
                bearish_reasons.append(f"RSI 낮음 ({stock_data['rsi14']:.1f})")

            return {
                "stock_code": stock_data["stock_code"],
                "stock_name": stock_data["stock_name"],
                "market": stock_data["market"],
                "sector": stock_data["sector"],
                "analysis_type": "혼합 신호",
                "bullish_score": round(stock_data["bullish_score"], 1),
                "bearish_score": round(stock_data["bearish_score"], 1),
                "key_metrics": {
                    "daily_return": round(stock_data["daily_return"], 2),
                    "return_5d": round(stock_data["return_5d"], 2),
                    "return_20d": round(stock_data["return_20d"], 2),
                    "rsi14": round(stock_data["rsi14"], 1),
                },
                "bullish_signals": bullish_reasons if bullish_reasons else ["혼조"],
                "bearish_signals": bearish_reasons if bearish_reasons else ["혼조"],
                "note": "긍정과 부정 신호가 섞여있어 신중한 검토가 필요합니다",
            }

    @staticmethod
    def _generate_market_overview(
        stocks_with_names: List[Dict[str, Any]], analysis_date: date
    ) -> Dict[str, Any]:
        """시장 종합 의견 생성"""
        if not stocks_with_names:
            return {}

        total_stocks = len(stocks_with_names)
        bullish_count = sum(1 for s in stocks_with_names if s["bullish_score"] >= 70)
        bearish_count = sum(1 for s in stocks_with_names if s["bearish_score"] >= 70)
        neutral_count = total_stocks - bullish_count - bearish_count

        avg_daily_return = sum(s["daily_return"] for s in stocks_with_names) / total_stocks
        bullish_ratio = (bullish_count / total_stocks * 100) if total_stocks > 0 else 0
        bearish_ratio = (bearish_count / total_stocks * 100) if total_stocks > 0 else 0

        # 시장 의견 생성
        if bullish_ratio > 20:
            market_sentiment = "긍정적 흐름"
            sentiment_reason = f"강세 신호 종목이 {bullish_count}개({bullish_ratio:.1f}%)로 높은 수준"
        elif bearish_ratio > 20:
            market_sentiment = "부정적 흐름"
            sentiment_reason = f"약세 신호 종목이 {bearish_count}개({bearish_ratio:.1f}%)로 높은 수준"
        else:
            market_sentiment = "혼조 흐름"
            sentiment_reason = "강세와 약세 신호가 섞여있는 상황"

        return {
            "analysis_date": str(analysis_date),
            "total_analyzed_stocks": total_stocks,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "bullish_ratio": round(bullish_ratio, 1),
            "bearish_ratio": round(bearish_ratio, 1),
            "neutral_ratio": round(100 - bullish_ratio - bearish_ratio, 1),
            "average_daily_return": round(avg_daily_return, 2),
            "market_sentiment": market_sentiment,
            "sentiment_reason": sentiment_reason,
        }

    @staticmethod
    def _generate_summary(
        bullish_stocks: List[Dict[str, Any]],
        bearish_stocks: List[Dict[str, Any]],
        market_overview: Dict[str, Any],
    ) -> str:
        """분석 결과 요약 생성"""
        lines = []

        lines.append("## 📊 시장 분석 요약\n")

        # 시장 전체 의견
        if market_overview:
            lines.append(
                f"**시장 흐름**: {market_overview.get('market_sentiment', '혼조')}"
            )
            lines.append(f"- {market_overview.get('sentiment_reason', '')}\n")

        # 강세 종목 요약
        if bullish_stocks:
            lines.append(f"**강세 예상 종목**: {len(bullish_stocks)}개")
            for stock in bullish_stocks[:3]:
                lines.append(
                    f"- {stock['stock_name']} (점수: {stock.get('bullish_score', 0)})"
                )
            lines.append("")

        # 약세 종목 요약
        if bearish_stocks:
            lines.append(f"**약세 주의 종목**: {len(bearish_stocks)}개")
            for stock in bearish_stocks[:3]:
                lines.append(
                    f"- {stock['stock_name']} (점수: {stock.get('bearish_score', 0)})"
                )
            lines.append("")

        # 분석 주의
        lines.append(
            "⚠️ **주의**: 본 분석은 참고용이며 투자 판단은 사용자 본인 책임입니다."
        )

        return "\n".join(lines)

    @staticmethod
    def save_analysis_report(
        analysis_result: Dict[str, Any], reports_dir: str = "reports"
    ) -> str:
        """
        분석 결과를 JSON 파일로 저장

        Args:
            analysis_result: 분석 결과 dict
            reports_dir: 리포트 저장 디렉토리

        Returns:
            저장된 파일 경로
        """
        import os
        from datetime import datetime

        os.makedirs(reports_dir, exist_ok=True)

        analysis_date = analysis_result.get("analysis_date", "unknown")
        filename = f"market_analysis_{analysis_date}.json"
        filepath = os.path.join(reports_dir, filename)

        # 저장 시간 추가
        analysis_result["saved_at"] = datetime.now().isoformat()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        logger.info(f"분석 리포트 저장됨: {filepath}")
        return filepath
