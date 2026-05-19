import requests
import json

try:
    response = requests.post(
        'http://localhost:8000/api/analysis/market-date-analysis',
        params={
            'analysis_date': '2026-05-18',
            'top_count': 5
        },
        timeout=60
    )
    
    print(f'Status Code: {response.status_code}')
    if response.status_code == 200:
        data = response.json()
        
        print('\n===== 2026-05-18 시장 분석 결과 =====\n')
        
        # 강세 종목
        if 'bullish_stocks' in data and data['bullish_stocks']:
            print('📈 강세 예상 종목:')
            for i, stock in enumerate(data['bullish_stocks'][:5], 1):
                print(f'\n{i}. {stock.get("name", "")} ({stock.get("code", "")})')
                print(f'   강도: {stock.get("bullish_score", 0)}/100')
                if 'reasons' in stock:
                    print(f'   근거: {", ".join(stock["reasons"][:3])}')
        
        # 약세 종목
        if 'bearish_stocks' in data and data['bearish_stocks']:
            print('\n\n📉 약세 주의 종목:')
            for i, stock in enumerate(data['bearish_stocks'][:5], 1):
                print(f'\n{i}. {stock.get("name", "")} ({stock.get("code", "")})')
                print(f'   위험도: {stock.get("bearish_score", 0)}/100')
                if 'risk_reasons' in stock:
                    print(f'   위험요소: {", ".join(stock["risk_reasons"][:3])}')
        
        # 시장 종합
        if 'market_overview' in data:
            print(f'\n\n📊 시장 종합 분석:')
            overview = data['market_overview']
            print(f'{overview.get("summary", "")}')
        
        # 분석 요약
        if 'analysis_summary' in data:
            print(f'\n💡 분석 요약:')
            print(f'{data["analysis_summary"]}')
            
    else:
        print(f'Error Response: {response.text}')
except Exception as e:
    print(f'Exception: {str(e)}')
