# 📊 특정 날짜 시장 분석 시스템 가이드

## 개요

**stock_market_analyzer** 프로젝트에 새로운 커스텀 명령어 시스템이 구현되었습니다.

사용자가 특정 날짜를 지정하면 자동으로 시장 분석을 수행하고, 강세/약세 종목을 정리한 분석 리포트를 생성합니다.

---

## 🎯 기능

### 1. 자동 시장 분석

- 지정된 날짜의 모든 종목에 대해 분석 실행
- 강세 예상 TOP N 종목 자동 추출
- 약세 주의 TOP N 종목 자동 추출
- 혼합 신호 종목 식별

### 2. 상세 분석 리포트 생성

**각 종목별:**
- 현재가 및 수익률 (당일, 5일, 20일, 60일)
- 기술 지표 (RSI14, 거래량 비율 등)
- 분석 근거 3~5개 제시
- 초보자 친화형 설명

**시장 종합:**
- 강세/약세/중립 종목 비율
- 전체 시장 흐름 평가
- 투자 참고 의견

### 3. JSON 형식 리포트 저장

```
reports/market_analysis_2026-05-20.json
```

---

## 📋 API 엔드포인트

### 1. POST 메서드 (권장)

```bash
POST /api/analysis/market-date-analysis
    ?analysis_date=2026-05-20
    &top_count=5
    &include_mixed=true
    &save_report=true
```

**파라미터:**
- `analysis_date` (필수): 분석 대상 날짜 (YYYY-MM-DD 형식)
- `top_count` (선택): 상위 N개 종목 (기본값 5, 최대 20)
- `include_mixed` (선택): 혼합 신호 종목 포함 여부 (기본값 true)
- `save_report` (선택): 리포트 파일 저장 여부 (기본값 true)

**응답 예시:**
```json
{
  "status": "success",
  "analysis_date": "2026-05-20",
  "bullish_stocks": [...],      // 강세 예상 종목 TOP 5
  "bearish_stocks": [...],      // 약세 주의 종목 TOP 5
  "mixed_signal_stocks": [...], // 혼합 신호 종목
  "market_overview": {          // 시장 종합 의견
    "total_analyzed_stocks": 2769,
    "bullish_count": 62,
    "bearish_count": 1452,
    "bullish_ratio": 2.2,
    "bearish_ratio": 52.4,
    "market_sentiment": "부정적 흐름"
  },
  "analysis_summary": "...",    // 분석 요약 텍스트
  "report_saved": "reports/market_analysis_2026-05-20.json",
  "disclaimer": "본 분석은 참고용이며..."
}
```

---

### 2. GET 메서드 (경로 기반)

```bash
GET /api/analysis/market-date-analysis/2026-05-20
    ?top_count=5
    &include_mixed=true
```

동일한 결과를 반환합니다.

---

## 💻 Python 코드 예시

### 기본 사용

```python
from app.services.market_date_analysis_service import MarketDateAnalysisService
from datetime import date

# 특정 날짜 분석
result = MarketDateAnalysisService.analyze_market_by_date(
    analysis_date=date(2026, 5, 20),
    top_count=5
)

# 결과 출력
print(f"분석 날짜: {result['analysis_date']}")
print(f"강세 종목: {len(result['bullish_stocks'])}개")
print(f"약세 종목: {len(result['bearish_stocks'])}개")
```

### 리포트 저장

```python
# 자동으로 저장됨 (save_report=True인 경우)
filepath = result.get('report_saved')
print(f"리포트 저장: {filepath}")

# 또는 수동 저장
filepath = MarketDateAnalysisService.save_analysis_report(result)
```

### 결과 확인

```python
# 강세 종목 순회
for stock in result['bullish_stocks']:
    print(f"\n종목: {stock['stock_name']} ({stock['stock_code']})")
    print(f"강세점수: {stock['bullish_score']}")
    print(f"분석근거:")
    for reason in stock['reasoning']:
        print(f"  - {reason}")
```

---

## 🔍 출력 데이터 상세 설명

### 강세 종목 분석

```json
{
  "stock_code": "033240",
  "stock_name": "자화전자",
  "market": "KOSPI",
  "sector": "반도체",
  "analysis_type": "강세 예상",
  "bullish_score": 100.0,
  "key_metrics": {
    "daily_return": 16.53,        // 당일 수익률 (%)
    "return_5d": 16.28,           // 5일 수익률 (%)
    "return_20d": 59.14,          // 20일 수익률 (%)
    "rsi14": 67.5,                // RSI 14일 지표
    "volume_ratio_5d": 5.49       // 거래량 비율 (5일 평균 대비)
  },
  "reasoning": [
    "당일 16.53% 상승으로 강한 매수 심리",
    "최근 5일 16.28% 상승으로 상승 추세 형성",
    "거래량이 평소의 5.5배로 증가"
  ],
  "note": "강한 상승 신호를 보이고 있습니다"
}
```

### 약세 종목 분석

```json
{
  "stock_code": "307870",
  "stock_name": "비투엔",
  "market": "KOSDAQ",
  "sector": "IT",
  "analysis_type": "약세 주의",
  "bearish_score": 97.0,
  "key_metrics": {
    "daily_return": -9.96,
    "return_5d": -17.11,
    "return_20d": -23.0,
    "rsi14": 15.4,
    "volume_ratio_5d": 3.34
  },
  "reasoning": [
    "당일 9.96% 하락으로 약한 심리",
    "최근 5일 17.11% 하락으로 하락 추세",
    "RSI14가 15.4로 약한 모멘텀",
    "약세 지표가 복합적으로 발생 중"
  ],
  "risk_warning": "약세 신호가 나타나고 있으니 주의가 필요합니다"
}
```

### 시장 종합 의견

```json
{
  "analysis_date": "2026-05-16",
  "total_analyzed_stocks": 2769,
  "bullish_count": 62,
  "bearish_count": 1452,
  "neutral_count": 1255,
  "bullish_ratio": 2.2,
  "bearish_ratio": 52.4,
  "neutral_ratio": 45.3,
  "average_daily_return": -0.25,
  "market_sentiment": "부정적 흐름",
  "sentiment_reason": "약세 신호 종목이 1452개(52.4%)로 높은 수준"
}
```

---

## ⚙️ 기술 사항

### 구현된 파일

1. **서비스 클래스**
   - `app/services/market_date_analysis_service.py`
   - MarketDateAnalysisService 클래스 포함

2. **API 라우트**
   - `app/api/market_date_analysis_routes.py`
   - 3개 엔드포인트 구현

3. **메인 앱**
   - `app/main.py` 수정
   - 라우트 등록 및 문서화

### 주요 메서드

#### `analyze_market_by_date()`
- 매개변수: analysis_date, top_count, include_mixed_signals
- 반환: 분석 결과 dictionary

#### `save_analysis_report()`
- 분석 결과를 JSON 파일로 저장
- 저장 경로: `reports/market_analysis_{DATE}.json`

### 데이터 소스

- **DB 테이블**: stock_analysis_results
- **분석 대상**: 모든 활성 종목
- **분석 지표**: bullish_score, bearish_score, 기술 지표 등

---

## 🚀 사용 시나리오

### 시나리오 1: 일일 시장 분석

```bash
# 어제(2026-05-20) 시장 분석
curl -X POST "http://localhost:8000/api/analysis/market-date-analysis?analysis_date=2026-05-20&top_count=10&save_report=true"
```

### 시나리오 2: 특정 기간 분석

```python
from datetime import date, timedelta

# 지난 주 5개 거래일 분석
start_date = date(2026, 5, 16)
for i in range(5):
    current_date = start_date - timedelta(days=i)
    result = MarketDateAnalysisService.analyze_market_by_date(current_date)
    MarketDateAnalysisService.save_analysis_report(result)
```

### 시나리오 3: 리포트 생성 및 활용

```bash
# 최신 분석 리포트 조회
GET /api/analysis/market-date-analysis/2026-05-20

# 결과를 파일로 저장
curl -X GET "http://localhost:8000/api/analysis/market-date-analysis/2026-05-20" > analysis_result.json

# 파일 처리
cat analysis_result.json | jq '.bullish_stocks[] | {code, name, score}'
```

---

## 📝 제약 조건 및 주의사항

### 1. 투자 권유 금지

- ❌ 금지: "매수 추천", "매도 추천", "급등 확정", "반드시 상승"
- ✅ 허용: "강세 신호", "약세 주의", "관찰 필요"

### 2. 데이터 가용성

- 분석 날짜에 대한 분석 결과가 DB에 존재해야 함
- 없으면 "no_data" 상태 반환

### 3. 성능 고려

- 전체 종목 분석이므로 대량의 데이터 처리
- top_count는 기본값 5 사용 권장

---

## ✅ 구현 완료 항목

- [x] 새로운 서비스 클래스 생성
- [x] API 엔드포인트 추가 (POST, GET)
- [x] 강세/약세 종목 자동 분류
- [x] 분석 근거 3~5개 제시
- [x] JSON 형식 리포트 저장
- [x] 초보자 친화형 설명
- [x] 시장 종합 의견 생성
- [x] 기존 DB 구조 유지
- [x] 기존 파일 구조 유지
- [x] 투자 추천 표현 금지

---

## 🔗 관련 링크

- **분석 기본**: `/api/analysis/bullish` (강세 종목)
- **분석 기본**: `/api/analysis/bearish` (약세 종목)
- **API 문서**: `/docs` (Swagger UI)

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `server.log`
2. DB 연결 확인: `GET /health`
3. 분석 데이터 존재 확인: 해당 날짜에 분석 실행 필요

---

**마지막 업데이트**: 2026-05-16
**상태**: ✅ 완료 및 테스트 완료
