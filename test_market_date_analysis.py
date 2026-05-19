#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
특정 날짜 시장 분석 시스템 테스트 스크립트

테스트 내용:
1. 서비스 클래스 기본 기능
2. 리포트 저장
3. 결과 검증
"""
import sys
import io
import json
from datetime import date
from pathlib import Path

# UTF-8 인코딩 설정
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.market_date_analysis_service import MarketDateAnalysisService


def test_basic_analysis():
    """기본 분석 테스트"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Market Analysis")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=3
        )
        
        # 결과 검증
        assert result.get("status") == "success", f"Status is {result.get('status')}"
        assert "bullish_stocks" in result, "Missing bullish_stocks"
        assert "bearish_stocks" in result, "Missing bearish_stocks"
        assert "market_overview" in result, "Missing market_overview"
        
        print(f"[PASS] Status: {result['status']}")
        print(f"[PASS] Date: {result['analysis_date']}")
        print(f"[PASS] Bullish stocks: {len(result['bullish_stocks'])} items")
        print(f"[PASS] Bearish stocks: {len(result['bearish_stocks'])} items")
        print(f"[PASS] Mixed signals: {len(result.get('mixed_signal_stocks', []))} items")
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_bullish_stocks_detail():
    """강세 종목 상세 정보 테스트"""
    print("\n" + "=" * 60)
    print("TEST 2: Bullish Stocks Details")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=2
        )
        
        bullish = result['bullish_stocks']
        if not bullish:
            print("[WARN] No bullish stocks found")
            return True
        
        stock = bullish[0]
        
        # 필드 검증
        required_fields = ['stock_code', 'stock_name', 'bullish_score', 'reasoning']
        for field in required_fields:
            assert field in stock, f"Missing {field}"
            print(f"[PASS] {field}: {stock[field]}")
        
        # 분석 근거 확인
        assert len(stock['reasoning']) > 0, "No reasoning provided"
        print(f"[PASS] {len(stock['reasoning'])} reasoning items:")
        for i, reason in enumerate(stock['reasoning'], 1):
            print(f"   {i}. {reason}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_bearish_stocks_detail():
    """약세 종목 상세 정보 테스트"""
    print("\n" + "=" * 60)
    print("TEST 3: Bearish Stocks Details")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=2
        )
        
        bearish = result['bearish_stocks']
        if not bearish:
            print("[WARN] No bearish stocks found")
            return True
        
        stock = bearish[0]
        
        # 필드 검증
        required_fields = ['stock_code', 'stock_name', 'bearish_score', 'reasoning']
        for field in required_fields:
            assert field in stock, f"Missing {field}"
            print(f"[PASS] {field}: {stock[field]}")
        
        # 위험 경고 확인
        if 'risk_warning' in stock:
            print(f"[PASS] Risk warning: {stock['risk_warning']}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_market_overview():
    """시장 종합 의견 테스트"""
    print("\n" + "=" * 60)
    print("TEST 4: Market Overview")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=5
        )
        
        overview = result['market_overview']
        
        # 필드 검증
        required_fields = [
            'total_analyzed_stocks',
            'bullish_count',
            'bearish_count',
            'market_sentiment'
        ]
        
        for field in required_fields:
            assert field in overview, f"Missing {field}"
            print(f"[PASS] {field}: {overview[field]}")
        
        # 비율 검증
        total = overview['total_analyzed_stocks']
        bullish = overview['bullish_count']
        bearish = overview['bearish_count']
        
        print(f"\nMarket Structure:")
        print(f"  - Bullish: {bullish} items ({overview['bullish_ratio']}%)")
        print(f"  - Bearish: {bearish} items ({overview['bearish_ratio']}%)")
        print(f"  - Neutral: {overview.get('neutral_count', 0)} items ({overview['neutral_ratio']}%)")
        print(f"\nMarket Sentiment: {overview['market_sentiment']}")
        print(f"   Reason: {overview['sentiment_reason']}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_report_save():
    """리포트 저장 테스트"""
    print("\n" + "=" * 60)
    print("TEST 5: Report Save")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=3
        )
        
        filepath = MarketDateAnalysisService.save_analysis_report(result)
        
        # 파일 존재 확인
        assert Path(filepath).exists(), f"Report file not found: {filepath}"
        print(f"[PASS] Report saved: {filepath}")
        
        # 파일 크기 확인
        file_size = Path(filepath).stat().st_size
        print(f"[PASS] File size: {file_size:,} bytes")
        
        # 파일 내용 검증
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data['status'] == 'success', "Saved data status is not success"
        assert 'saved_at' in data, "Missing saved_at timestamp"
        print(f"[PASS] Saved at: {data['saved_at']}")
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_no_data_handling():
    """데이터 없음 처리 테스트"""
    print("\n" + "=" * 60)
    print("TEST 6: No Data Handling")
    print("=" * 60)
    
    try:
        # 존재하지 않는 날짜로 분석
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2020, 1, 1)
        )
        
        if result.get('status') == 'no_data':
            print(f"[PASS] Normal handling: {result['message']}")
            return True
        elif result.get('status') == 'success':
            print(f"[WARN] Data found for this date: {result['analysis_date']}")
            return True
        else:
            print(f"[ERROR] Unexpected status: {result.get('status')}")
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_analysis_summary():
    """분석 요약 테스트"""
    print("\n" + "=" * 60)
    print("TEST 7: Analysis Summary")
    print("=" * 60)
    
    try:
        result = MarketDateAnalysisService.analyze_market_by_date(
            analysis_date=date(2026, 5, 16),
            top_count=3
        )
        
        summary = result.get('analysis_summary', '')
        assert summary, "No analysis summary"
        
        print(f"[PASS] Analysis Summary:\n")
        print(summary)
        
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    """모든 테스트 실행"""
    print("\n" + "=" * 60)
    print("Market Date Analysis System Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Analysis", test_basic_analysis),
        ("Bullish Stocks Details", test_bullish_stocks_detail),
        ("Bearish Stocks Details", test_bearish_stocks_detail),
        ("Market Overview", test_market_overview),
        ("Report Save", test_report_save),
        ("No Data Handling", test_no_data_handling),
        ("Analysis Summary", test_analysis_summary),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n[ERROR] {test_name} test failed: {e}")
            results.append((test_name, False))
    
    # 최종 결과
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
