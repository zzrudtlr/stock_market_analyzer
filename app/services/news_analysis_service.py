"""
뉴스 감성 분석 서비스

Google 뉴스 RSS / 네이버 파이낸스 / DART 공시(DB)에서 헤드라인을 수집하고
GPT-4o-mini로 호재/악재/중립 분류 후 news_sentiment_results에 저장합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 모든 결과는 참고용 뉴스 감성 분석 정보입니다.
"""
import json
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, text

from app.database import get_db_session
from app.models.disclosure import Disclosure
from app.models.news_sentiment_result import NewsSentimentResult
from app.models.stock import Stock

logger = logging.getLogger(__name__)


# ── 뉴스 수집 ────────────────────────────────────────────────────

def _fetch_google_news(stock_name: str, limit: int = 20) -> list[dict]:
    """Google 뉴스 RSS로 종목 관련 헤드라인 수집."""
    results = []
    queries = [
        f"{stock_name} 주가",
        f"{stock_name} 실적 계약",
    ]
    seen: set[str] = set()
    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is None or not title_el.text:
                    continue
                title = title_el.text.strip()
                if title in seen:
                    continue
                seen.add(title)
                results.append({"title": title, "source": "google"})
                if len(results) >= limit:
                    return results
        except Exception as e:
            logger.debug(f"[뉴스] Google RSS 오류 (쿼리={query}): {e}")
    return results


def _fetch_naver_news(stock_code: str, limit: int = 20) -> list[dict]:
    """네이버 파이낸스 종목 뉴스 HTML 스크래핑 (best-effort)."""
    results = []
    try:
        url = (
            f"https://finance.naver.com/item/news_news.naver"
            f"?code={stock_code}&page=1&sm=title_entity_id.basic&clusterId="
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.naver.com",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        # 네이버 파이낸스는 EUC-KR 인코딩
        try:
            html = raw.decode("euc-kr", errors="replace")
        except Exception:
            html = raw.decode("utf-8", errors="replace")

        # <td class="title"> 내 <a> 태그 파싱
        import re
        pattern = re.compile(
            r'<td[^>]*class="title"[^>]*>.*?<a[^>]*>([^<]{5,})</a>',
            re.DOTALL,
        )
        seen: set[str] = set()
        for m in pattern.finditer(html):
            title = m.group(1).strip()
            title = re.sub(r"\s+", " ", title)
            if len(title) < 5 or title in seen:
                continue
            seen.add(title)
            results.append({"title": title, "source": "naver"})
            if len(results) >= limit:
                break
    except Exception as e:
        logger.debug(f"[뉴스] 네이버 파이낸스 스크래핑 오류 ({stock_code}): {e}")
    return results


def _fetch_dart_news(stock_code: str, session, days: int = 14) -> list[dict]:
    """DB Disclosure 테이블에서 최근 공시 제목 수집."""
    results = []
    try:
        cutoff = date.today() - timedelta(days=days)
        rows = session.execute(
            select(Disclosure.title, Disclosure.disclosure_type)
            .where(
                Disclosure.stock_code == stock_code,
                Disclosure.report_date >= cutoff,
            )
            .order_by(Disclosure.report_date.desc())
            .limit(20)
        ).all()
        for row in rows:
            title = row.title
            if not title:
                continue
            results.append({"title": title.strip(), "source": "dart"})
    except Exception as e:
        logger.debug(f"[뉴스] DART DB 조회 오류 ({stock_code}): {e}")
    return results


# ── 점수 / 시그널 ─────────────────────────────────────────────────

def _calc_score(positive: int, negative: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((positive - negative) / total * 100, 4)


def _determine_signal(score: float) -> str:
    if score > 50:
        return "강한 호재"
    if score > 20:
        return "호재 우세"
    if score >= -20:
        return "중립"
    if score >= -50:
        return "악재 우세"
    return "강한 악재"


# ── DB 저장 ───────────────────────────────────────────────────────

def _upsert(session, stock_code: str, analysis_date: date, data: dict) -> None:
    """ON DUPLICATE KEY UPDATE 방식 upsert."""
    fields = {
        "total_news_count":    data.get("total_news_count", 0),
        "positive_news_count": data.get("positive_news_count", 0),
        "negative_news_count": data.get("negative_news_count", 0),
        "neutral_news_count":  data.get("neutral_news_count", 0),
        "google_news_count":   data.get("google_news_count", 0),
        "naver_news_count":    data.get("naver_news_count", 0),
        "dart_news_count":     data.get("dart_news_count", 0),
        "news_sentiment_score":  data.get("news_sentiment_score", 0),
        "news_sentiment_signal": data.get("news_sentiment_signal", "중립"),
        "headlines_json":      data.get("headlines_json"),
        "ai_sentiment_summary": data.get("ai_sentiment_summary"),
        "ai_key_issues":        data.get("ai_key_issues"),
        "ai_sentiment_risk":    data.get("ai_sentiment_risk"),
    }
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(
        "INSERT INTO news_sentiment_results "
        "(stock_code, analysis_date, "
        + ", ".join(fields.keys())
        + ") VALUES (:stock_code, :analysis_date, "
        + ", ".join(f":{k}" for k in fields)
        + f") ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    session.execute(sql, {"stock_code": stock_code, "analysis_date": analysis_date, **fields})
    session.commit()


# ── 메인 분석 ────────────────────────────────────────────────────

def analyze_news_sentiment(
    stock_code: str,
    analysis_date: date,
    with_ai: bool = True,
) -> dict:
    """
    단일 종목 뉴스 감성 분석 → DB 저장.

    Returns:
        {status, stock_code, total, positive, negative, neutral, score, signal}
    """
    session = get_db_session()
    try:
        # 종목명 조회
        stock = session.execute(
            select(Stock).where(Stock.stock_code == stock_code)
        ).scalar_one_or_none()
        stock_name = stock.stock_name if stock else stock_code

        # 헤드라인 수집
        google_items = _fetch_google_news(stock_name, limit=20)
        naver_items  = _fetch_naver_news(stock_code, limit=20)
        dart_items   = _fetch_dart_news(stock_code, session, days=14)

        all_headlines = google_items + naver_items + dart_items

        # 중복 제거
        seen: set[str] = set()
        unique_headlines: list[dict] = []
        for h in all_headlines:
            t = h["title"].strip()
            if t and t not in seen:
                seen.add(t)
                unique_headlines.append(h)

        if not unique_headlines:
            logger.info(f"[뉴스] {stock_code} 수집된 헤드라인 없음")
            return {"status": "no_data", "stock_code": stock_code}

        # AI 감성 분류
        ai_result: dict = {}
        classifications: list[dict] = []

        if with_ai:
            from app.services.news_ai_service import classify_news_sentiment
            ai_result = classify_news_sentiment(unique_headlines, stock_name, analysis_date)
            classifications = ai_result.get("classifications", [])

        # AI 분류 결과가 있으면 사용, 없으면 전체를 중립으로 처리
        if classifications:
            # AI 분류 결과를 헤드라인에 매핑 (순서 기반)
            enriched: list[dict] = []
            cls_map = {c["title"]: c for c in classifications}
            for h in unique_headlines:
                cls = cls_map.get(h["title"], {})
                enriched.append({
                    "title":     h["title"],
                    "source":    h["source"],
                    "sentiment": cls.get("sentiment", "중립"),
                    "reason":    cls.get("reason", ""),
                })
            positive = sum(1 for e in enriched if e["sentiment"] == "호재")
            negative = sum(1 for e in enriched if e["sentiment"] == "악재")
            neutral  = sum(1 for e in enriched if e["sentiment"] == "중립")
        else:
            enriched = [
                {"title": h["title"], "source": h["source"], "sentiment": "중립", "reason": ""}
                for h in unique_headlines
            ]
            positive = negative = 0
            neutral = len(enriched)

        total = len(enriched)
        score  = _calc_score(positive, negative, total)
        signal = _determine_signal(score)

        google_cnt = sum(1 for e in enriched if e["source"] == "google")
        naver_cnt  = sum(1 for e in enriched if e["source"] == "naver")
        dart_cnt   = sum(1 for e in enriched if e["source"] == "dart")

        data = {
            "total_news_count":    total,
            "positive_news_count": positive,
            "negative_news_count": negative,
            "neutral_news_count":  neutral,
            "google_news_count":   google_cnt,
            "naver_news_count":    naver_cnt,
            "dart_news_count":     dart_cnt,
            "news_sentiment_score":  score,
            "news_sentiment_signal": signal,
            "headlines_json":       json.dumps(enriched, ensure_ascii=False),
            "ai_sentiment_summary": ai_result.get("ai_sentiment_summary"),
            "ai_key_issues":        ai_result.get("ai_key_issues"),
            "ai_sentiment_risk":    ai_result.get("ai_sentiment_risk"),
        }
        _upsert(session, stock_code, analysis_date, data)

        logger.info(
            f"[뉴스] {stock_code} {stock_name} "
            f"전체={total} 호재={positive} 악재={negative} 중립={neutral} "
            f"점수={score:.1f} 시그널={signal}"
        )
        return {
            "status": "success",
            "stock_code": stock_code,
            "stock_name": stock_name,
            "total": total,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "score": score,
            "signal": signal,
        }
    except Exception as e:
        logger.error(f"[뉴스] {stock_code} 분석 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "stock_code": stock_code, "message": str(e)}
    finally:
        session.close()


# ── 배치 ─────────────────────────────────────────────────────────

def run_news_batch(
    analysis_date: Optional[date] = None,
    limit: int = 80,
    delay_sec: float = 0.2,
) -> dict:
    """
    관심종목 + 분석점수 상위 종목 뉴스 감성 배치 분석.

    Args:
        analysis_date: 기준일 (None이면 오늘)
        limit: 최대 처리 종목 수
        delay_sec: 종목 간 대기
    """
    if analysis_date is None:
        analysis_date = date.today()

    session = get_db_session()
    try:
        from app.models.watchlist import WatchlistItem
        watchlist_codes = set(
            session.execute(
                select(WatchlistItem.stock_code)
            ).scalars().all()
        )

        from app.models.analysis import StockAnalysisResult
        top_codes = list(
            session.execute(
                select(StockAnalysisResult.stock_code)
                .where(StockAnalysisResult.analysis_date == analysis_date)
                .order_by(StockAnalysisResult.bullish_score.desc())
                .limit(limit)
            ).scalars().all()
        )

        # 이미 당일 분석된 종목 제외
        already_done = set(
            session.execute(
                select(NewsSentimentResult.stock_code)
                .where(NewsSentimentResult.analysis_date == analysis_date)
            ).scalars().all()
        )
    finally:
        session.close()

    all_targets = list(dict.fromkeys(list(watchlist_codes) + top_codes))[:limit]
    target_codes = [c for c in all_targets if c not in already_done]

    if not all_targets:
        return {"status": "no_data", "message": f"{analysis_date} 분석 대상 종목 없음"}

    logger.info(
        f"[뉴스배치] 시작 — 전체 {len(all_targets)}개 중 신규 {len(target_codes)}개 / {analysis_date}"
        f" (기존 {len(already_done)}개 스킵)"
    )

    success = errors = 0
    skipped = len(already_done)
    for code in target_codes:
        r = analyze_news_sentiment(code, analysis_date, with_ai=True)
        if r.get("status") == "success":
            success += 1
        elif r.get("status") == "no_data":
            skipped += 1
        else:
            errors += 1
        if delay_sec > 0:
            time.sleep(delay_sec)

    status = "success" if errors == 0 else "partial"
    return {
        "status": status,
        "analysis_date": str(analysis_date),
        "total": len(all_targets),
        "success": success,
        "skipped": skipped,
        "errors": errors,
        "already_skipped": len(already_done),
    }


# ── DB 읽기 ───────────────────────────────────────────────────────

def _row_to_dict(row: NewsSentimentResult) -> dict:
    return {
        "stock_code":           row.stock_code,
        "analysis_date":        str(row.analysis_date),
        "total_news_count":     row.total_news_count,
        "positive_news_count":  row.positive_news_count,
        "negative_news_count":  row.negative_news_count,
        "neutral_news_count":   row.neutral_news_count,
        "google_news_count":    row.google_news_count,
        "naver_news_count":     row.naver_news_count,
        "dart_news_count":      row.dart_news_count,
        "news_sentiment_score":  float(row.news_sentiment_score) if row.news_sentiment_score is not None else 0.0,
        "news_sentiment_signal": row.news_sentiment_signal or "중립",
        "headlines_json":        row.headlines_json,
        "ai_sentiment_summary":  row.ai_sentiment_summary,
        "ai_key_issues":         row.ai_key_issues,
        "ai_sentiment_risk":     row.ai_sentiment_risk,
        "updated_at":            str(row.updated_at) if row.updated_at else "-",
    }


def get_news_sentiment(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> Optional[dict]:
    """단일 종목 최신 뉴스 감성 결과 조회."""
    session = get_db_session()
    try:
        q = select(NewsSentimentResult).where(
            NewsSentimentResult.stock_code == stock_code
        )
        if analysis_date:
            q = q.where(NewsSentimentResult.analysis_date == analysis_date)
        q = q.order_by(NewsSentimentResult.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_news_sentiment_top(
    analysis_date: Optional[date] = None,
    limit: int = 50,
    signal: Optional[str] = None,
) -> list[dict]:
    """뉴스 감성 점수 상위/하위 종목 조회."""
    session = get_db_session()
    try:
        if analysis_date is None:
            # 가장 최신 기준일 사용
            latest = session.execute(
                select(NewsSentimentResult.analysis_date)
                .order_by(NewsSentimentResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(NewsSentimentResult).where(
            NewsSentimentResult.analysis_date == analysis_date
        )
        if signal:
            q = q.where(NewsSentimentResult.news_sentiment_signal == signal)
        q = q.order_by(NewsSentimentResult.news_sentiment_score.desc()).limit(limit)
        rows = session.execute(q).scalars().all()
        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()
