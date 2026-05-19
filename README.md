# Stock Market Analyzer

한국 주식 시장 데이터 분석 도구 (MVP 1단계)

> ⚠️ **투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다.**  
> 이 프로그램은 투자 추천/매수·매도 지시가 아니라 데이터 기반 분석 보조 도구입니다.

---

## 기술 스택

| 역할 | 기술 |
| --- | --- |
| Backend | FastAPI + Uvicorn |
| DB | MySQL + SQLAlchemy ORM |
| 데이터 수집 | FinanceDataReader, pykrx |
| 분석 | pandas, numpy |
| 차트 | plotly |
| 대시보드 | Streamlit |

---

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

```bash
cp .env.example .env
# .env 파일을 열어 DB 정보 입력
```

`.env` 예시:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=yourpassword
MYSQL_DATABASE=stock_market_analyzer
```

---

## 실행

### FastAPI 서버
```bash
python app/main.py
# 또는
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 문서: http://localhost:8000/docs

### Streamlit 대시보드
```bash
streamlit run app/dashboard/streamlit_app.py
```

대시보드: http://localhost:8501

---

## MVP 1단계 워크플로우

DB 테이블이 이미 생성되어 있다고 가정합니다.

### 1. 종목 리스트 수집

```bash
curl -X POST http://localhost:8000/api/collect/stocks
```

### 2. 시장 지수 수집 (KOSPI, KOSDAQ)

```bash
curl -X POST "http://localhost:8000/api/collect/indices?days=60"
```

### 3. 시세 데이터 수집 (최근 60일)

시간이 걸리므로 백그라운드로 실행합니다.

```bash
curl -X POST "http://localhost:8000/api/collect/prices/bulk?days=60&background=true"
```

또는 전체를 한 번에:

```bash
curl -X POST "http://localhost:8000/api/collect/all?days=60"
```

### 4. 분석 실행

```bash
curl -X POST http://localhost:8000/api/analysis/run
```

### 5. 리포트 생성

```bash
curl -X POST http://localhost:8000/api/reports/generate
```

생성된 리포트는 `reports/` 폴더에 저장됩니다.

---

## 주요 API 엔드포인트

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/` | 엔드포인트 목록 |
| GET | `/health` | DB 연결 상태 |
| POST | `/api/collect/stocks` | 종목 리스트 수집 |
| POST | `/api/collect/prices` | 오늘 시세 수집 |
| POST | `/api/collect/prices/bulk` | N일 시세 일괄 수집 |
| POST | `/api/collect/indices` | 시장 지수 수집 |
| GET | `/api/stocks` | 종목 목록 |
| GET | `/api/stocks/{code}` | 종목 상세 |
| GET | `/api/stocks/{code}/prices` | 종목 시세 |
| GET | `/api/analysis/summary` | 시그널별 종목 수 |
| GET | `/api/analysis/bullish` | 강세 TOP20 |
| GET | `/api/analysis/bearish` | 약세 TOP20 |
| POST | `/api/analysis/run` | 분석 실행 |
| GET | `/api/reports/latest` | 최신 리포트 JSON |
| GET | `/api/reports/latest/markdown` | 최신 리포트 Markdown |
| POST | `/api/reports/generate` | 리포트 생성 |

---

## 프로젝트 구조

```
stock_market_analyzer/
├── app/
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── config.py               # 설정 (.env 로드)
│   ├── database.py             # SQLAlchemy 엔진/세션
│   ├── models/                 # ORM 모델 (DB 구조 그대로)
│   │   ├── stock.py            # stocks 테이블
│   │   ├── price.py            # stock_daily_prices 테이블
│   │   ├── market.py           # market_indices 테이블
│   │   ├── disclosure.py       # disclosures 테이블
│   │   ├── analysis.py         # stock_analysis_results 테이블
│   │   ├── report.py           # daily_market_reports 테이블
│   │   ├── watchlist.py        # watchlist_groups/items 테이블
│   │   └── collector_log.py    # collector_logs 테이블
│   ├── collectors/
│   │   ├── krx_collector.py    # pykrx 기반 일별 시세 수집
│   │   └── finance_data_reader_collector.py  # FDR 기반 수집
│   ├── analyzers/
│   │   └── score_calculator.py # 강세/약세 점수 계산
│   ├── services/
│   │   ├── stock_service.py    # 종목 조회
│   │   ├── price_service.py    # 시세 조회
│   │   ├── analysis_service.py # 분석 실행/조회
│   │   └── report_service.py   # 리포트 생성
│   ├── api/
│   │   ├── stock_routes.py     # 종목 API
│   │   ├── analysis_routes.py  # 분석 API
│   │   └── report_routes.py    # 리포트 API
│   ├── dashboard/
│   │   └── streamlit_app.py    # Streamlit 대시보드
│   └── utils/
│       ├── logger.py           # 로깅 설정
│       ├── date_utils.py       # 날짜 유틸
│       └── retry.py            # 재시도 데코레이터
├── data/
├── reports/                    # 생성된 Markdown 리포트
├── logs/                       # 로그 파일
├── requirements.txt
└── .env.example
```

---

## DB 규칙

- 테이블은 이미 생성되어 있음
- DROP TABLE / ALTER TABLE 절대 금지
- 컬럼명 변경 금지
- 모든 INSERT는 upsert (ON DUPLICATE KEY UPDATE)
- stock_code 기준으로 테이블 간 논리적 연결
