#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-05-18 주식시장 분석"""

from app.services.market_date_analysis_service import MarketDateAnalysisService
from datetime import date
import json

# 2026-05-18 시장 분석 실행
print('시장 분석 중...')
result = MarketDateAnalysisService.analyze_market_by_date(
    analysis_date=date(2026, 5, 18),
    top_count=10
)

print('='*60)
print(f'분석 날짜: {result["analysis_date"]}')
print(f'분석 상태: {result["status"]}')
print('='*60)

if result['status'] == 'success':
    # 시장 개요
    overview = result['market_overview']
    print(f'\n📊 시장 개요')
    print(f'분석 종목 수: {overview["total_analyzed_stocks"]:,}개')
    print(f'강세 비율: {overview["bullish_ratio"]:.1f}%')
    print(f'약세 비율: {overview["bearish_ratio"]:.1f}%')
    print(f'시장 심리: {overview["market_sentiment"]}')
    
    # 강세 종목
    print(f'\n📈 강세 TOP 10 종목')
    for i, stock in enumerate(result['bullish_stocks'][:10], 1):
        print(f'{i}. {stock["stock_name"]} ({stock["stock_code"]})')
        print(f'   강세점수: {stock["bullish_score"]:.1f}점')
        if stock['reasoning']:
            print(f'   이유: {stock["reasoning"][0]}')
    
    # 약세 종목
    print(f'\n📉 약세 TOP 10 종목')
    for i, stock in enumerate(result['bearish_stocks'][:10], 1):
        print(f'{i}. {stock["stock_name"]} ({stock["stock_code"]})')
        print(f'   약세점수: {stock["bearish_score"]:.1f}점')
        if stock['reasoning']:
            print(f'   이유: {stock["reasoning"][0]}')
else:
    print(f'분석 실패: {result.get("message", "알 수 없음")}')

# 삼성전자 정보 조회
print(f'\n' + '='*60)
print(f'삼성전자(005930) 상세 분석')
print('='*60)
all_stocks = result['bullish_stocks'] + result['bearish_stocks']
samsung = next((s for s in all_stocks if s['stock_code'] == '005930'), None)
if samsung:
    print(f'회사명: {samsung["stock_name"]}')
    print(f'종목코드: {samsung["stock_code"]}')
    if 'bullish_score' in samsung and samsung['bullish_score'] > 0:
        print(f'강세점수: {samsung["bullish_score"]:.1f}점')
    if 'bearish_score' in samsung and samsung['bearish_score'] > 0:
        print(f'약세점수: {samsung["bearish_score"]:.1f}점')
    if samsung['reasoning']:
        print(f'분석 근거:')
        for reason in samsung['reasoning']:
            print(f'  - {reason}')
else:
    print('삼성전자 분석 데이터가 없습니다.')

# 결과 JSON 저장 위치
print(f'\n✅ 상세 분석 결과는 다음 파일에 저장되었습니다:')
print(f'   reports/market_analysis_2026-05-18.json')
