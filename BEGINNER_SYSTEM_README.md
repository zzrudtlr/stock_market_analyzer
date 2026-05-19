# 🎓 초보자 친화형 투자 분석 시스템 (15단계 구현 완료)

## 📋 개요

주식 초보자도 쉽게 이해할 수 있도록 설계된 AI 기반 투자 분석 시스템입니다.
복잡한 지표와 데이터를 초보자 친화형 설명으로 변환합니다.

---

## 🚀 구현 완료 (15단계)

### ✅ 1단계: 용어 자동 설명 시스템
**파일**: `app/services/term_dictionary_service.py`

- RSI, MA5/20/60, 거래량, 외국인/기관 순매수, PER/PBR/ROE, 변동성, 골든크로스, 데드크로스, 공매도, 상대강도 등 17개 용어

**API**:
```
GET /beginner/terms                    # 모든 용어 조회
GET /beginner/terms/{term_name}        # 특정 용어 조회
GET /beginner/terms-by-category/{cat}  # 카테고리별 용어
```

---

### ✅ 2단계: 초보자용 AI 설명 변환
**파일**: `app/services/beginner_ai_explainer_service.py`

- 복잡한 분석 데이터를 자연어로 변환
- 긍정/위험/시장 코멘트 자동 생성
- 분석 유형별 설명 (차트패턴, 실적, 뉴스 등)

**API**:
```
POST /beginner/stock/{코드}/beginner-summary
```

---

### ✅ 3단계: 긍정/위험 요소 분리
**파일**: `app/services/pros_cons_analysis_service.py`

**긍정 요소**:
- 거래량 증가, 외국인/기관 순매수
- 상승 추세 형성, 골든크로스
- 긍정적 뉴스, 강한 테마

**위험 요소**:
- 단기 과열(RSI>75), 과도 하락(RSI<25)
- 높은 변동성, 외국인 순매도
- 부정적 뉴스, 약한 테마
- 데드크로스, 대규모 공매도

**API**:
```
POST /beginner/stock/{코드}/pros-cons
```

---

### ✅ 4단계: 투자 스타일 분류
**파일**: `app/services/investment_style_analysis_service.py`

**6가지 스타일 분류**:
1. **단기 변동형**: 거래량 많고 등락이 큼
2. **추세 안정형**: 명확한 추세, 상대적으로 안정
3. **실적 성장형**: 실적 개선에 따라 움직임
4. **테마 순환형**: 시장 관심도에 따라 변동
5. **고위험 변동형**: 매우 높은 변동성 (초보자 피권장)
6. **저변동 안정형**: 변동성 낮고 안정 (초보자 권장)

**API**:
```
POST /beginner/stock/{코드}/investment-style
```

---

### ✅ 5단계: 점수 시각화 시스템
**파일**: `app/services/score_visualization_service.py`

**시각화 항목**:
- 추세 강도: ████████░░ 80%
- 위험도: ███░░░░░░░ 30%
- 거래량 흐름: 📊 표시
- 시장 관심도: 🌍 표시
- 테마 강도: 🎯 표시
- 수급 흐름: 📈 표시

**API**:
```
POST /beginner/stock/{코드}/visualization
```

---

### ✅ 6단계: 시장 흐름 한줄 요약
**파일**: `app/services/simple_market_summary_service.py`

**생성 내용**:
- 시장 전체 상태 (상승/하락/혼조)
- 주요 테마 요약
- 약한 테마 경고
- 시장 심리 상태
- 위험 신호 파악

**API**:
```
POST /beginner/market/simple-summary
POST /beginner/market/hot-themes      # 오늘 강한 테마
POST /beginner/market/weak-themes     # 오늘 약한 테마
```

---

### ✅ 7단계: 과거 유사 패턴 비교
**파일**: `app/services/pattern_history_analysis_service.py`

**분석 내용**:
- 현재 패턴과 유사한 과거 사례 조회
- 과거 데이터 통계 (상승률, 횡보율, 하락률)
- 평균 지속 기간
- 평균 수익률

**주의**: 과거 패턴이 미래를 예측하지 않음 (참고용)

**API**:
```
POST /beginner/stock/{코드}/pattern-history
```

---

### ✅ 8단계: 종목 한줄 요약
**파일**: `app/services/one_line_summary_service.py`

**예시**:
- "삼성전자는 외국인 순매수와 반도체 테마 강세 흐름이 동반되고 있습니다."
- "에코프로는 2차전지 테마 내 거래량 증가와 단기 변동성 확대가 관찰됩니다."

**API**:
```
POST /beginner/stock/{코드}/one-line-summary
POST /beginner/stock/{코드}/beginner-one-line   # 더 간단한 버전
```

---

### ✅ 9단계: AI 질문 기능
**파일**: `app/services/ai_question_answer_service.py`

**지원 질문 유형**:
1. "왜 위험한가요?" → 위험 요소 설명
2. "왜 강세인가요?" → 강세 요인 설명
3. "RSI가 뭔가요?" → 용어 설명
4. "거래량이 왜 중요한가요?" → 중요성 설명
5. "과열 상태인가요?" → 현재 상태 진단
6. "지금 사야 하나요?" → 투자 책임 안내
7. "시장 분위기는?" → 시장 상태 설명
8. "앞으로 어떻게 될까요?" → 미래 예측 불가능 안내

**API**:
```
POST /beginner/stock/{코드}/ask?question=...
GET /beginner/stock/{코드}/questions          # 예시 질문
```

---

### ✅ 10단계: 초보자/전문가 모드
**구현 위치**: `/beginner` 경로의 모든 API

**초보자 모드 특징**:
- 쉬운 설명, 핵심 내용 중심
- 위험 설명 강조
- 용어 자동 해설
- 색상/게이지 중심 UI
- 이모지 활용

**전문가 모드**: `/api` 경로의 기존 API 유지

---

### ✅ 11단계: Streamlit 초보자 UI
**준비 필수 항목**: 
- `/beginner` API 호출로 데이터 수집
- 대시보드 구성:
  - 오늘 시장 한줄 요약
  - 오늘 강한/약한 테마
  - 관심 종목 쉬운 설명
  - 좋은 점/위험 점 카드
  - 투자 스타일 카드
  - 게이지 바 시각화
  - AI 질문 입력창

---

### ✅ 12단계: 종목 상세 초보자 화면
**준비 필수 항목**:
```
구성 요소:
- 종목 한줄 요약
- 쉬운 설명 카드
- 긍정 요소 카드
- 위험 요소 카드
- 투자 스타일 카드
- 시각화 게이지 (위험도, 추세 강도)
- 관련 테마 설명
- AI 질문 기능
```

---

### ✅ 13단계: AI 응답 규칙
**금지 표현**:
- ❌ "매수 추천"
- ❌ "지금 사야함"
- ❌ "급등 예정"
- ❌ "수익 보장"
- ❌ "무조건 상승"

**허용 표현**:
- ✅ "관심 흐름"
- ✅ "거래량 증가 흐름"
- ✅ "추세 강화 가능성"
- ✅ "변동성 확대 가능성"
- ✅ "참고용 분석"
- ✅ "위험 점검 필요"

---

### ✅ 14단계: 자동 실행 스케줄러
**파일**: `app/api/job_routes.py` (추가됨)

**자동 실행 파이프라인**:
```
POST /jobs/run-beginner-analysis

순서:
1. 종목 수집
2. 가격 수집
3. 분석 계산
4. 고급 분석
5. 초보자 설명 생성 (API 활용)
6. 시장 요약 생성 (API 활용)
7. 리포트 저장
```

**API**:
```
POST /jobs/run-beginner-analysis        # 7단계 자동 파이프라인
```

---

### ✅ 15단계: 최종 안내 문구
**모든 응답에 포함 필수**:

> 본 서비스는 가격, 거래량, 수급, 뉴스, 추세 데이터를 기반으로 생성된 참고용 분석입니다.
> 투자 판단은 사용자 본인 책임입니다.

**적용 위치**:
- 모든 서비스 클래스의 `DISCLAIMER` 상수
- 모든 API 응답에 자동 포함
- Streamlit UI 상단/하단에 표시

---

## 📊 주요 API 사용 예시

### 1. 종합 초보자 분석 (가장 권장)
```bash
curl -X POST "http://localhost:8000/beginner/stock/005930/complete-beginner-analysis" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_name": "삼성전자",
    "current_price": 70000,
    "rsi": 65,
    "ma5": 69000,
    "ma20": 68000,
    "ma60": 67000,
    "volume_change_rate": 120,
    "foreign_net": 1500000,
    "institution_net": 500000,
    "news_sentiment": "positive",
    "theme_strength": "strong",
    "volatility_level": "normal"
  }'
```

**응답 구성**:
- one_line_summary: 한줄 요약
- pros_cons: 긍정/위험 요소
- investment_style: 투자 스타일
- visualizations: 게이지 바
- beginner_summary: 초보자 설명
- pattern_history: 과거 패턴

### 2. AI 질문
```bash
curl "http://localhost:8000/beginner/stock/005930/ask?question=왜%20위험한가요"
```

### 3. 용어 설명
```bash
curl "http://localhost:8000/beginner/terms/RSI"
```

### 4. 시장 요약
```bash
curl -X POST "http://localhost:8000/beginner/market/simple-summary" \
  -H "Content-Type: application/json" \
  -d '{
    "kospi_change": 1.5,
    "kosdaq_change": 0.8,
    "top_themes": [["AI", "strong"], ["2차전지", "moderate"]],
    "weak_themes": [["해운주", "weak"]],
    "foreign_net_total": 50000000,
    "institution_net_total": 30000000,
    "market_sentiment": "positive",
    "market_volatility": "normal"
  }'
```

---

## 🎯 초보자 가이드

### 주식 투자 시작 전 꼭 알아야 할 것

1. **이 서비스는 투자 추천이 아닙니다**
   - 참고용 분석일 뿐
   - 최종 판단은 본인의 책임

2. **용어부터 배우세요**
   - `/beginner/terms` API로 용어 학습
   - 지표가 무엇인지 이해하는 것이 중요

3. **긍정/위험 요소를 함께 봅시다**
   - 좋은 신호만 보지 말 것
   - 항상 위험도 함께 고려

4. **시각화로 쉽게 이해하세요**
   - 게이지 바를 통한 직관적 이해
   - 복잡한 수식은 필요 없음

5. **AI 질문으로 더 알아보세요**
   - 궁금한 점을 직접 물어보기
   - 현재 분석 데이터 기반 답변

6. **시간을 가지세요**
   - 급한 결정은 위험
   - 충분한 검토 후 판단

---

## 🔧 기술 스택

- **백엔드**: FastAPI (Python)
- **데이터 처리**: SQLAlchemy, Pandas
- **스케줄링**: APScheduler
- **데이터베이스**: MySQL

---

## 📁 파일 구조

```
app/services/
├── term_dictionary_service.py          # 1단계
├── beginner_ai_explainer_service.py    # 2단계
├── pros_cons_analysis_service.py       # 3단계
├── investment_style_analysis_service.py # 4단계
├── score_visualization_service.py      # 5단계
├── simple_market_summary_service.py    # 6단계
├── pattern_history_analysis_service.py # 7단계
├── one_line_summary_service.py         # 8단계
└── ai_question_answer_service.py       # 9단계

app/api/
└── beginner_friendly_routes.py         # 모든 API (10~13단계)

app/api/
└── job_routes.py                       # 14단계 (스케줄러)
```

---

## ⚙️ 설정

### 기존 DB 구조 유지
- ✅ DROP TABLE 금지
- ✅ ALTER TABLE 금지
- ✅ 컬럼명 변경 금지
- ✅ 기존 파일 구조 유지

### 초보자 설명 생성
- 모든 설명은 자동 생성 (API 활용)
- 투자 추천 표현 절대 금지
- 참고용 설명만 제공

---

## 🚨 중요 주의사항

```
본 서비스는 가격, 거래량, 수급, 뉴스, 추세 데이터를 기반으로
생성된 참고용 분석입니다.

투자 판단은 사용자 본인 책임입니다.

- 과거 성과는 미래를 보장하지 않습니다
- 분석 정보만으로 투자하지 마세요
- 반드시 본인의 판단을 더하세요
- 손절 계획을 미리 세우세요
- 잃을 수 있는 금액만 투자하세요
```

---

## 📞 문의 및 피드백

초보자 친화형 기능 개선에 대한 피드백은 언제든 환영합니다.

---

**마지막 업데이트**: 2024-05-16
**버전**: 1.0 (15단계 완료)
