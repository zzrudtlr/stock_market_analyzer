"""
테마 강세/약세 분석 서비스 (v2)

data/theme_mapping.json 에 정의된 32개 테마 기준으로 종목을 분류하고
stock_analysis_results 지표를 집계하여 6단계 시그널과 AI 해설을 생성합니다.

주의:
- 투자 추천, 매수/매도 권유 시스템이 아닙니다.
- 모든 분석 결과는 참고용 시장 흐름 정보입니다.
"""
import json
import logging
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import func as _sf, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.stock import Stock
from app.models.theme_analysis import ThemeAnalysis
from app.models.theme_analysis_result import ThemeAnalysisResult

logger = logging.getLogger(__name__)

# ── 테마 매핑 로드 ────────────────────────────────────────────────

_MAPPING_PATH = Path(__file__).parent.parent.parent / "data" / "theme_mapping.json"
_THEME_MAP: dict[str, dict] = {}


def _load_theme_map() -> dict[str, dict]:
    global _THEME_MAP
    if _THEME_MAP:
        return _THEME_MAP
    try:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            data = json.load(f)
        _THEME_MAP = data.get("themes", {})
        logger.info(f"[테마매핑] {len(_THEME_MAP)}개 테마 로드 완료")
    except Exception as e:
        logger.error(f"[테마매핑] 로드 실패: {e}")
        _THEME_MAP = {}
    return _THEME_MAP


def _build_code_theme_map() -> dict[str, str]:
    """stock_code -> theme_name 역방향 매핑"""
    theme_map = _load_theme_map()
    result: dict[str, str] = {}
    for theme_name, info in theme_map.items():
        for s in info.get("stocks", []):
            code = s.get("code", "")
            if code and code not in result:  # 첫 번째 테마 우선
                result[code] = theme_name
    return result


def _build_code_name_map() -> dict[str, str]:
    """stock_code -> stock_name (JSON 기반)"""
    theme_map = _load_theme_map()
    result: dict[str, str] = {}
    for info in theme_map.values():
        for s in info.get("stocks", []):
            result[s.get("code", "")] = s.get("name", "")
    return result


# ── 6단계 시그널 결정 ─────────────────────────────────────────────

def _determine_signal(avg_r5d: float, avg_r1d: float, bullish_ratio: float,
                      bearish_ratio: float, avg_volume_ratio: float,
                      momentum_avg: float, risk_avg: float) -> str:
    """
    6단계: 매우 강세 / 강세 흐름 / 순환매 관심 / 혼조 / 약세 흐름 / 하락 주의
    """
    if avg_r5d >= 4.0 or (avg_r5d >= 2.0 and bullish_ratio >= 65):
        return "매우 강세"
    if avg_r5d >= 1.5 and bullish_ratio >= 50:
        return "강세 흐름"
    if avg_volume_ratio >= 1.5 and abs(avg_r5d) < 2.0 and bullish_ratio >= 35:
        return "순환매 관심"
    if avg_r5d <= -4.0 or (risk_avg >= 20 and avg_r5d < -1.0):
        return "하락 주의"
    if avg_r5d <= -1.5 and bearish_ratio >= 50:
        return "약세 흐름"
    return "혼조"


# ── 뉴스 수집 ─────────────────────────────────────────────────────

def _fetch_theme_news(theme_name: str, limit: int = 6) -> list[str]:
    from urllib.parse import quote
    theme_map = _load_theme_map()
    query = theme_map.get(theme_name, {}).get("news_query", f"{theme_name} 주식 시황")
    url = (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl=ko&gl=KR&ceid=KR:ko"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        titles = []
        for item in root.findall(".//item"):
            el = item.find("title")
            if el is not None and el.text:
                title = el.text.rsplit(" - ", 1)[0].strip()
                if title:
                    titles.append(title)
        return titles[:limit]
    except Exception as e:
        logger.warning(f"[뉴스] {theme_name} 수집 실패: {e}")
        return []


def _fetch_all_news(theme_names: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {n: [] for n in theme_names}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_theme_news, n): n for n in theme_names}
        for future in as_completed(futures, timeout=20):
            name = futures[future]
            try:
                result[name] = future.result()
            except Exception:
                pass
    return result


# ── 스포트라이트 종목 추출 ──────────────────────────────────────────

def _pick_spotlight(items: list[dict], code_name_map: dict[str, str]) -> dict:
    if not items:
        return {}

    def _stock_info(item, key, label):
        val = item.get(key, 0)
        code = item.get("stock_code", "")
        name = code_name_map.get(code) or item.get("stock_name") or code
        return {"code": code, "name": name, label: round(float(val or 0), 2)}

    sorted_r5 = sorted(items, key=lambda x: float(x.get("return_5d") or 0))
    sorted_vol = sorted(items, key=lambda x: float(x.get("volume_ratio_5d") or 0), reverse=True)
    sorted_mom = sorted(items, key=lambda x: float(x.get("momentum_score") or 0), reverse=True)
    sorted_risk= sorted(items, key=lambda x: float(x.get("risk_score") or 0), reverse=True)

    return {
        "strongest": _stock_info(sorted_r5[-1], "return_5d", "return_5d"),
        "weakest":   _stock_info(sorted_r5[0],  "return_5d", "return_5d"),
        "volume_leader":    _stock_info(sorted_vol[0],  "volume_ratio_5d", "volume_ratio"),
        "momentum_leader":  _stock_info(sorted_mom[0],  "momentum_score",  "momentum_score"),
        "risk_warning":     _stock_info(sorted_risk[0], "risk_score",      "risk_score"),
    }


# ── DB upsert (theme_analysis_results) ────────────────────────────

def _upsert_result(session, analysis_date: date, theme_name: str,
                   stats: dict, spotlight: dict, ai: dict):
    spotlight_json = lambda k: json.dumps(spotlight.get(k, {}), ensure_ascii=False) if spotlight.get(k) else None

    values = dict(
        analysis_date=analysis_date,
        theme_name=theme_name,
        theme_signal=stats["theme_signal"],
        avg_return_1d=stats["avg_return_1d"],
        avg_return_5d=stats["avg_return_5d"],
        avg_return_20d=stats["avg_return_20d"],
        avg_volume_ratio=stats["avg_volume_ratio"],
        bullish_ratio=stats["bullish_ratio"],
        bearish_ratio=stats["bearish_ratio"],
        momentum_avg=stats["momentum_avg"],
        trend_avg=stats["trend_avg"],
        risk_avg=stats["risk_avg"],
        stock_count=stats["stock_count"],
        stock_codes=stats["stock_codes"],
        strongest_stock=spotlight_json("strongest"),
        weakest_stock=spotlight_json("weakest"),
        volume_leader=spotlight_json("volume_leader"),
        momentum_leader=spotlight_json("momentum_leader"),
        risk_warning_stock=spotlight_json("risk_warning"),
        ai_theme_summary=ai.get("ai_theme_summary"),
        ai_theme_risk=ai.get("ai_theme_risk"),
        ai_theme_flow=ai.get("ai_theme_flow"),
        ai_theme_volume_comment=ai.get("ai_theme_volume_comment"),
        ai_theme_rotation_comment=ai.get("ai_theme_rotation_comment"),
    )
    update_vals = {k: v for k, v in values.items()
                   if k not in ("analysis_date", "theme_name")}
    update_vals["updated_at"] = _sf.now()

    stmt = (
        mysql_insert(ThemeAnalysisResult)
        .values(**values)
        .on_duplicate_key_update(**update_vals)
    )
    session.execute(stmt)


# ── 레거시 호환: 구 theme_analysis 테이블에도 함께 저장 ────────────

def _upsert_legacy(session, report_date: date, theme_name: str, stats: dict,
                   ai: dict):
    values = dict(
        report_date=report_date,
        theme_name=theme_name,
        stock_codes=stats.get("stock_codes"),
        stock_count=stats.get("stock_count", 0),
        avg_return_1d=stats.get("avg_return_1d"),
        avg_return_5d=stats.get("avg_return_5d"),
        avg_return_20d=stats.get("avg_return_20d"),
        avg_bullish_score=stats.get("momentum_avg"),
        avg_bearish_score=stats.get("risk_avg"),
        bullish_count=round(stats.get("bullish_ratio", 0) * stats.get("stock_count", 0) / 100),
        bearish_count=round(stats.get("bearish_ratio", 0) * stats.get("stock_count", 0) / 100),
        theme_signal=stats.get("theme_signal"),
        ai_summary=ai.get("ai_theme_summary"),
        ai_reason=ai.get("ai_theme_flow"),
        ai_outlook=ai.get("ai_theme_risk"),
    )
    update_vals = {k: v for k, v in values.items()
                   if k not in ("report_date", "theme_name")}
    update_vals["updated_at"] = _sf.now()
    stmt = (
        mysql_insert(ThemeAnalysis)
        .values(**values)
        .on_duplicate_key_update(**update_vals)
    )
    session.execute(stmt)


# ── 공개 API ──────────────────────────────────────────────────────

def run_theme_analysis(report_date: Optional[date] = None) -> dict:
    """
    당일 분석 데이터를 32개 테마별로 집계하고 AI 해설을 생성하여 DB에 저장합니다.
    참고용 시장 흐름 분석 결과이며 투자 권유가 아닙니다.
    """
    target_date = report_date or date.today()

    code_theme_map = _build_code_theme_map()
    code_name_map  = _build_code_name_map()

    if not code_theme_map:
        return {"status": "error", "message": "테마 매핑 데이터 없음"}

    session = get_db_session()
    try:
        # 1. 당일 분석결과 + 종목 조인
        rows = session.execute(
            select(
                StockAnalysisResult.stock_code,
                StockAnalysisResult.daily_return,
                StockAnalysisResult.return_5d,
                StockAnalysisResult.return_20d,
                StockAnalysisResult.volume_ratio_5d,
                StockAnalysisResult.volume_ratio_20d,
                StockAnalysisResult.momentum_score,
                StockAnalysisResult.trend_score,
                StockAnalysisResult.risk_score,
                StockAnalysisResult.bullish_score,
                StockAnalysisResult.bearish_score,
                StockAnalysisResult.final_signal,
                Stock.stock_name,
            )
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code)
            .where(
                StockAnalysisResult.analysis_date == target_date,
                Stock.is_active == 1,
            )
        ).all()

        if not rows:
            return {"status": "no_data", "date": str(target_date),
                    "message": "분석 데이터 없음 — 분석을 먼저 실행하세요"}

        # 2. 테마별 그룹화 (JSON 매핑 우선)
        from collections import defaultdict
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            theme = code_theme_map.get(r.stock_code)
            if theme:
                groups[theme].append({
                    "stock_code":      r.stock_code,
                    "stock_name":      r.stock_name or code_name_map.get(r.stock_code, ""),
                    "daily_return":    float(r.daily_return    or 0),
                    "return_5d":       float(r.return_5d       or 0),
                    "return_20d":      float(r.return_20d      or 0),
                    "volume_ratio_5d": float(r.volume_ratio_5d or 0),
                    "momentum_score":  float(r.momentum_score  or 0),
                    "trend_score":     float(r.trend_score     or 0),
                    "risk_score":      float(r.risk_score      or 0),
                    "bullish_score":   float(r.bullish_score   or 0),
                    "bearish_score":   float(r.bearish_score   or 0),
                    "final_signal":    r.final_signal or "",
                })

        # 3. 테마별 집계
        theme_stats_list: list[dict] = []
        for theme_name, items in groups.items():
            if len(items) < 2:  # 2종목 미만 제외
                continue

            n = len(items)
            avg_r1d  = sum(i["daily_return"]    for i in items) / n
            avg_r5d  = sum(i["return_5d"]       for i in items) / n
            avg_r20d = sum(i["return_20d"]      for i in items) / n
            avg_vol  = sum(i["volume_ratio_5d"] for i in items) / n
            mom_avg  = sum(i["momentum_score"]  for i in items) / n
            trd_avg  = sum(i["trend_score"]     for i in items) / n
            risk_avg = sum(i["risk_score"]      for i in items) / n

            bull_n = sum(1 for i in items if "강세" in i["final_signal"])
            bear_n = sum(1 for i in items if "약세" in i["final_signal"] or "하락" in i["final_signal"])
            bull_ratio = round(bull_n / n * 100, 1)
            bear_ratio = round(bear_n / n * 100, 1)

            signal = _determine_signal(
                avg_r5d, avg_r1d, bull_ratio, bear_ratio, avg_vol, mom_avg, risk_avg
            )
            spotlight = _pick_spotlight(items, code_name_map)

            theme_stats_list.append({
                "theme_name": theme_name,
                "items":      items,
                "spotlight":  spotlight,
                "stats": {
                    "theme_signal":    signal,
                    "stock_count":     n,
                    "stock_codes":     json.dumps([i["stock_code"] for i in items]),
                    "avg_return_1d":   round(avg_r1d,  4),
                    "avg_return_5d":   round(avg_r5d,  4),
                    "avg_return_20d":  round(avg_r20d, 4),
                    "avg_volume_ratio":round(avg_vol,  4),
                    "bullish_ratio":   bull_ratio,
                    "bearish_ratio":   bear_ratio,
                    "momentum_avg":    round(mom_avg,  4),
                    "trend_avg":       round(trd_avg,  4),
                    "risk_avg":        round(risk_avg, 4),
                },
            })

        if not theme_stats_list:
            return {
                "status": "no_themes",
                "date": str(target_date),
                "message": "분류된 테마가 없습니다. theme_mapping.json의 종목코드를 확인하세요.",
            }

        # 4. 뉴스 수집 (병렬)
        theme_names = [t["theme_name"] for t in theme_stats_list]
        logger.info(f"[테마분석] 뉴스 수집 시작 — {len(theme_names)}개 테마")
        news_map = _fetch_all_news(theme_names)
        fetched = sum(1 for v in news_map.values() if v)
        logger.info(f"[테마분석] 뉴스 수집 완료 — {fetched}/{len(theme_names)}개 테마")

        # 5. AI 해설 생성
        from app.services.theme_ai_service import call_theme_ai
        ai_map = call_theme_ai(theme_stats_list, target_date, news_map)

        # 6. DB upsert
        success, errors = 0, 0
        for t in theme_stats_list:
            try:
                ai = ai_map.get(t["theme_name"], {})
                _upsert_result(session, target_date, t["theme_name"],
                               t["stats"], t["spotlight"], ai)
                _upsert_legacy(session, target_date, t["theme_name"], t["stats"], ai)
                success += 1
            except Exception as e:
                logger.error(f"[테마분석] {t['theme_name']} upsert 실패: {e}")
                session.rollback()
                errors += 1

        session.commit()
        logger.info(f"[테마분석] 완료 — {target_date} | {success}개 저장, {errors}개 오류")
        return {
            "status": "success",
            "date":   str(target_date),
            "themes": success,
            "errors": errors,
        }

    except Exception as e:
        session.rollback()
        logger.error(f"[테마분석] 실행 실패: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def get_theme_analysis(report_date: Optional[date] = None) -> list[dict]:
    """저장된 테마 분석 결과를 반환합니다 (5일 수익률 기준 정렬)."""
    target_date = report_date or date.today()
    session = get_db_session()
    try:
        rows = session.execute(
            select(ThemeAnalysisResult)
            .where(ThemeAnalysisResult.analysis_date == target_date)
            .order_by(ThemeAnalysisResult.avg_return_5d.desc())
        ).scalars().all()

        if not rows:
            # 레거시 테이블 폴백
            return _get_legacy_analysis(session, target_date)

        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()


def _row_to_dict(r: ThemeAnalysisResult) -> dict:
    def _parse_json(text):
        try:
            return json.loads(text) if text else {}
        except Exception:
            return {}

    return {
        "theme_name":      r.theme_name,
        "theme_signal":    r.theme_signal or "혼조",
        "stock_count":     r.stock_count or 0,
        "stock_codes":     json.loads(r.stock_codes or "[]"),
        "avg_return_1d":   float(r.avg_return_1d  or 0),
        "avg_return_5d":   float(r.avg_return_5d  or 0),
        "avg_return_20d":  float(r.avg_return_20d or 0),
        "avg_volume_ratio":float(r.avg_volume_ratio or 0),
        "bullish_ratio":   float(r.bullish_ratio  or 0),
        "bearish_ratio":   float(r.bearish_ratio  or 0),
        "momentum_avg":    float(r.momentum_avg   or 0),
        "trend_avg":       float(r.trend_avg      or 0),
        "risk_avg":        float(r.risk_avg       or 0),
        "strongest_stock": _parse_json(r.strongest_stock),
        "weakest_stock":   _parse_json(r.weakest_stock),
        "volume_leader":   _parse_json(r.volume_leader),
        "momentum_leader": _parse_json(r.momentum_leader),
        "risk_warning_stock": _parse_json(r.risk_warning_stock),
        "ai_theme_summary":          r.ai_theme_summary,
        "ai_theme_risk":             r.ai_theme_risk,
        "ai_theme_flow":             r.ai_theme_flow,
        "ai_theme_volume_comment":   r.ai_theme_volume_comment,
        "ai_theme_rotation_comment": r.ai_theme_rotation_comment,
        "updated_at": str(r.updated_at)[:16] if r.updated_at else "-",
    }


def _get_legacy_analysis(session, target_date: date) -> list[dict]:
    """theme_analysis(구 테이블) 폴백."""
    from app.models.theme_analysis import ThemeAnalysis
    rows = session.execute(
        select(ThemeAnalysis)
        .where(ThemeAnalysis.report_date == target_date)
        .order_by(ThemeAnalysis.avg_return_1d.desc())
    ).scalars().all()

    return [
        {
            "theme_name":      r.theme_name,
            "theme_signal":    r.theme_signal or "혼조",
            "stock_count":     r.stock_count or 0,
            "stock_codes":     json.loads(r.stock_codes or "[]"),
            "avg_return_1d":   float(r.avg_return_1d    or 0),
            "avg_return_5d":   float(r.avg_return_5d    or 0),
            "avg_return_20d":  float(r.avg_return_20d   or 0),
            "avg_volume_ratio":float(r.avg_bullish_score or 0),
            "bullish_ratio":   0.0,
            "bearish_ratio":   0.0,
            "momentum_avg":    0.0,
            "trend_avg":       0.0,
            "risk_avg":        float(r.avg_bearish_score or 0),
            "strongest_stock": {},
            "weakest_stock":   {},
            "volume_leader":   {},
            "momentum_leader": {},
            "risk_warning_stock": {},
            "ai_theme_summary":          r.ai_summary,
            "ai_theme_risk":             r.ai_outlook,
            "ai_theme_flow":             r.ai_reason,
            "ai_theme_volume_comment":   None,
            "ai_theme_rotation_comment": None,
            "updated_at": str(r.updated_at)[:16] if r.updated_at else "-",
        }
        for r in rows
    ]


def get_themes_by_signal(signal: str, report_date: Optional[date] = None) -> list[dict]:
    """특정 시그널의 테마 목록 반환."""
    themes = get_theme_analysis(report_date)
    return [t for t in themes if t["theme_signal"] == signal]


def get_theme_detail(theme_name: str, report_date: Optional[date] = None) -> Optional[dict]:
    """특정 테마의 상세 정보 반환."""
    themes = get_theme_analysis(report_date)
    for t in themes:
        if t["theme_name"] == theme_name:
            return t
    return None
