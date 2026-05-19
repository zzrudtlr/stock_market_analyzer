# 🚀 특정 날짜 시장 분석 - 빠른 시작 가이드

> 5분 안에 시작하는 시장 분석 시스템

---

## 📍 1단계: 기본 사용법 (가장 간단함)

### Python 스크립트로 분석 실행

```python
from app.services.market_date_analysis_service import MarketDateAnalysisService
from datetime import date

# 2026-05-20 분석
result = MarketDateAnalysisService.analyze_market_by_date(
    analysis_date=date(2026, 5, 20),
    top_count=5
)

# 결과 확인
print(f"강세 종목: {len(result['bullish_stocks'])}개")
print(f"약세 종목: {len(result['bearish_stocks'])}개")
```

**저장된 리포트**: `reports/market_analysis_2026-05-20.json`

---

## 📍 2단계: API로 호출

### 방법 A: POST 메서드 (권장)

```bash
curl -X POST "http://localhost:8000/api/analysis/market-date-analysis" \
  -H "Content-Type: application/json" \
  -d "{\"analysis_date\": \"2026-05-20\", \"top_count\": 5}"
```

또는 쿼리 파라미터:

```bash
curl -X POST "http://localhost:8000/api/analysis/market-date-analysis?analysis_date=2026-05-20&top_count=5"
```

### 방법 B: GET 메서드 (경로)

```bash
curl -X GET "http://localhost:8000/api/analysis/market-date-analysis/2026-05-20?top_count=5"
```

---

## 📍 3단계: 결과 확인

### 응답 구조

```json
{
  "status": "success",
  "analysis_date": "2026-05-20",
  "bullish_stocks": [
    {
      "stock_code": "033240",
      "stock_name": "자화전자",
      "bullish_score": 100.0,
      "reasoning": [
        "당일 16.53% 상승으로 강한 매수 심리",
        "최근 5일 16.28% 상승으로 상승 추세 형성",
        "거래량이 평소의 5.5배로 증가"
      ]
    },
    ...
  ],
  "bearish_stocks": [...],
  "market_overview": {
    "total_analyzed_stocks": 2769,
    "bullish_ratio": 2.2,
    "bearish_ratio": 52.4,
    "market_sentiment": "부정적 흐름"
  }
}
```

---

## 🎯 자주 묻는 질문

### Q1: 어떤 날짜 분석이 가능한가?

**A**: DB에 분석 결과가 있는 날짜만 가능합니다.
- 기본 분석이 실행된 날짜
- 보통 거래일

### Q2: 강세/약세는 어떻게 결정되나?

**A**: 자동 계산된 점수 기반
- **강세**: bullish_score ≥ 70
- **약세**: bearish_score ≥ 70
- **혼합**: 50~70 범위

### Q3: 몇 개 종목까지 조회 가능한가?

**A**: top_count 파라미터로 조절
- 최소: 1개
- 최대: 20개
- 기본값: 5개

### Q4: JSON 파일은 어디 저장되나?

**A**: `reports/` 폴더
```
reports/market_analysis_2026-05-20.json
reports/market_analysis_2026-05-19.json
...
```

### Q5: 같은 날짜로 다시 분석하면?

**A**: 기존 파일을 덮어씀
- 새로운 분석 결과로 업데이트

---

## 💡 실용 예시

### 예시 1: 어제 시장 분석

```python
from app.services.market_date_analysis_service import MarketDateAnalysisService
from datetime import date, timedelta

yesterday = date.today() - timedelta(days=1)
result = MarketDateAnalysisService.analyze_market_by_date(yesterday, top_count=10)

# 강세 TOP 3
for i, stock in enumerate(result['bullish_stocks'][:3], 1):
    print(f"{i}. {stock['stock_name']} ({stock['bullish_score']}점)")
    for reason in stock['reasoning'][:2]:
        print(f"   - {reason}")
```

### 예시 2: 시장 심리 확인

```python
result = MarketDateAnalysisService.analyze_market_by_date(date(2026, 5, 20))
overview = result['market_overview']

print(f"시장 심리: {overview['market_sentiment']}")
print(f"강세 비율: {overview['bullish_ratio']}%")
print(f"약세 비율: {overview['bearish_ratio']}%")
```

### 예시 3: 특정 종목 찾기

```python
result = MarketDateAnalysisService.analyze_market_by_date(date(2026, 5, 20), top_count=20)

# 관심 종목 찾기
target_code = "005930"
for stock in result['bullish_stocks'] + result['bearish_stocks']:
    if stock['stock_code'] == target_code:
        print(f"{stock['stock_name']}: {stock}")
```

---

## ⚡ 성능 팁

### 1. 빠른 응답
```python
# 기본 (빠름)
result = MarketDateAnalysisService.analyze_market_by_date(
    date(2026, 5, 20), 
    top_count=5
)

# 상세 정보 필요 시
result = MarketDateAnalysisService.analyze_market_by_date(
    date(2026, 5, 20), 
    top_count=20
)
```

### 2. 리포트 저장 생략
```python
# 저장 안 함 (약 2배 빠름)
result = MarketDateAnalysisService.analyze_market_by_date(date)
# 수동 저장만
MarketDateAnalysisService.save_analysis_report(result)
```

---

## 🔧 문제 해결

### 문제: "no_data" 상태

```json
{
  "status": "no_data",
  "message": "2020-01-01 날짜의 분석 데이터가 없습니다."
}
```

**해결**: 분석이 실행된 거래일 선택

### 문제: 결과가 비어있음

```python
result['bullish_stocks']  # []
result['bearish_stocks']  # []
```

**해결**: 
- 다른 날짜 시도
- `top_count` 값 증가
- `include_mixed=true` 사용

### 문제: API 응답 느림

**해결**:
```python
# 최소화된 요청
result = MarketDateAnalysisService.analyze_market_by_date(
    date(2026, 5, 20),
    top_count=3,
    include_mixed_signals=False
)
```

---

## 📊 데이터 해석 팁

### 강세 점수 (Bullish Score)

| 범위 | 의미 |
|-----|------|
| 90+ | 강한 상승 신호 |
| 70~89 | 상승 신호 |
| 50~69 | 약한 상승 신호 |
| <50 | 신호 없음 |

### 약세 점수 (Bearish Score)

| 범위 | 의미 |
|-----|------|
| 90+ | 강한 하락 위험 |
| 70~89 | 하락 위험 |
| 50~69 | 약한 위험 신호 |
| <50 | 신호 없음 |

### 시장 심리 (Market Sentiment)

- **긍정적 흐름**: 강세 종목 비율 높음 (>20%)
- **부정적 흐름**: 약세 종목 비율 높음 (>20%)
- **혼조 흐름**: 강세/약세 균형 또는 중립 우위

---

## 🎓 학습 경로

1. **기본** (5분)
   - 데이터 구조 이해
   - 간단한 API 호출

2. **중급** (15분)
   - Python 스크립트 작성
   - 결과 분석 및 해석

3. **고급** (30분)
   - 대량 데이터 처리
   - 자동화 스크립트 작성
   - CSV 내보내기

---

## 📚 더 알아보기

- **상세 가이드**: `MARKET_DATE_ANALYSIS_GUIDE.md`
- **구현 보고서**: `IMPLEMENTATION_REPORT_MARKET_DATE_ANALYSIS.md`
- **API 문서**: `http://localhost:8000/docs`

---

## ✅ 체크리스트

시작 전 확인:
- [ ] 서버 실행 중 (`python app/main.py`)
- [ ] MySQL 연결됨 (`GET /health` → db: ok)
- [ ] 분석 데이터 존재 (`POST /api/analysis/run` 실행됨)

---

**지금 바로 시작하세요!** 🚀

```python
from app.services.market_date_analysis_service import MarketDateAnalysisService
from datetime import date

result = MarketDateAnalysisService.analyze_market_by_date(date(2026, 5, 20))
print(f"✅ 분석 완료: {result['analysis_date']}")
```
