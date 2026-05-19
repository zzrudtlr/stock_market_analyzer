"""
기업 펀더멘털(실적) 분석 서비스

데이터 소스:
  - pykrx : 당일 PER / PBR / EPS (시장 공시 기준)
  - 네이버 파이낸스 finsum_Y : 연간 매출·영업이익·순이익·ROE·부채비율 (최근 3개년)

계산 항목:
  revenue_growth / operating_income_growth / net_income_growth / eps_growth
  roe_score / debt_risk_score / valuation_score → fundamental_score(-100~+100)

주의:
  - 투자 추천, 매수/매도 권유 시스템이 아닙니다.
  - 모든 결과는 참고용 펀더멘털 분석 정보입니다.
"""
import json
import logging
import re
import time
import urllib.request
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, text

from app.config import settings
from app.database import get_db_session
from app.models.fundamental_analysis_result import FundamentalAnalysisResult
from app.models.stock import Stock

logger = logging.getLogger(__name__)

_BANNED = [
    "매수 추천", "매도 추천", "급등 확정", "반드시 상승",
    "수익 보장", "지금 사야", "추천 종목", "무조건 상승",
]

_AI_SYSTEM = """당신은 한국 주식 기업 실적·펀더멘털 분석 전문가입니다.

[역할]
재무 데이터를 기반으로 기업의 성장성·수익성·안정성·밸류에이션을 평가하고
시장 참여자가 이해할 수 있는 해설을 작성합니다.

[필수 준수 규칙]
1. 투자 추천·매수·매도 권유 절대 금지
2. 금지 표현: "매수 추천", "급등 확정", "반드시 상승", "수익 보장", "지금 사야함"
3. 허용 표현: "실적 흐름 확인", "주의 필요", "개선 가능성", "변동성 존재"
4. 한국어만 사용

[출력 형식 — JSON만 반환, 다른 텍스트 없음]
{
  "ai_fundamental_summary": "종합 실적·펀더멘털 평가 1~2문장",
  "ai_growth_comment": "매출/영업이익/순이익 성장 흐름 1~2문장",
  "ai_valuation_comment": "PER/PBR 기반 밸류에이션 해설 1~2문장",
  "ai_risk_comment": "부채비율·이익 감소 등 주의 사항 1~2문장"
}"""


# ── 데이터 수집 ───────────────────────────────────────────────────

def _safe_float(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.strip().replace(",", "").replace("%", "").replace("N/A", "").replace("-", "")
    try:
        return float(t) if t else None
    except ValueError:
        return None


def _fetch_pykrx_fundamental(stock_code: str, analysis_date: date) -> dict:
    """pykrx로 PER·PBR·EPS 조회 (최근 5 영업일 내 탐색)."""
    try:
        from pykrx import stock as krx
        for offset in range(5):
            d = analysis_date - timedelta(days=offset)
            date_str = d.strftime("%Y%m%d")
            try:
                df = krx.get_market_fundamental_by_date(date_str, date_str, stock_code)
                if df is not None and not df.empty:
                    row = df.iloc[-1]
                    per = float(row.get("PER", 0)) or None
                    pbr = float(row.get("PBR", 0)) or None
                    eps = int(row.get("EPS", 0)) or None
                    return {"per": per, "pbr": pbr, "eps": eps}
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[펀더멘털] pykrx 조회 오류 ({stock_code}): {e}")
    return {}


def _fetch_fnguide(stock_code: str) -> dict:
    """
    FnGuide 메인 페이지에서 연간 재무 데이터 스크래핑.

    반환 키 (리스트, 오래된 → 최신 순, 추정치 제외):
      revenue, op_income, net_income, debt_ratio  — 연간 실적 (억원)
      roe  — 투자지표 섹션 (%)
    """
    result: dict = {}
    try:
        url = (
            f"https://comp.fnguide.com/SVO2/ASP/SVD_main.asp"
            f"?pGB=1&gicode=A{stock_code}&cID=&MenuYn=Y&ReportGB=D&NewMenuID=Y&stkGb=701"
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://comp.fnguide.com/",
                "Accept-Language": "ko-KR,ko;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # ── 연간 재무 테이블 파싱 ──────────────────────────────
        # 행: <th scope="row" class="clf"><div>ROW_NAME</div></th>
        # 열: <td class="r ..." title="PRECISE_VALUE">DISPLAY</td>
        #     추정(E) 열은 tdbg_b 클래스 포함 → 제외
        # th 내부 전체 텍스트 추출 (div + span 혼재 처리)
        fin_row_pat = re.compile(
            r'<th[^>]*class="clf"[^>]*>(.*?)</th>'
            r'(.*?)(?=<tr[^>]*>|</tbody)',
            re.DOTALL,
        )
        # 실제 연간 열(추정 제외): tdbg_b 클래스 없는 <td>에서 title 또는 텍스트 추출
        td_actual_pat = re.compile(
            r'<td[^>]*class="[^"]*r[^"]*"[^>]*(?:title="(-?[\d.,]+)"[^>]*>|>)\s*(-?[\d.,]+)?\s*(?:<|$)'
        )
        td_estimate_pat = re.compile(r'tdbg_b')

        fin_target = {
            "매출액":    "revenue",
            "영업이익":  "op_income",
            "당기순이익": "net_income",
            "부채비율":  "debt_ratio",
        }

        for m in fin_row_pat.finditer(html):
            # th 내부 HTML 태그 제거해서 텍스트만 추출
            row_name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            for kw, key in fin_target.items():
                if kw in row_name and key not in result:
                    cells_html = m.group(2)
                    # <td> 단위로 분리 후 추정 열 제외
                    cell_chunks = re.split(r'(?=<td\s)', cells_html)
                    vals: list[Optional[float]] = []
                    for chunk in cell_chunks:
                        if td_estimate_pat.search(chunk):
                            continue  # 추정치(E) 열 스킵
                        tm = td_actual_pat.search(chunk)
                        if tm:
                            # title 속성값 우선, 없으면 텍스트 값 사용
                            raw_val = tm.group(1) or tm.group(2)
                            vals.append(_safe_float(raw_val))
                    # 연간 3개만 유지 (분기 데이터 혼입 방지)
                    annual_vals = [v for v in vals if v is not None][:4]
                    if annual_vals:
                        result[key] = annual_vals
                    break

        # ── ROE 섹션 파싱 (투자지표 영역) ────────────────────────
        # 구조: <th scope="row"><div>ROE</div></th><td class="r">X</td>...
        roe_m = re.search(
            r'<th[^>]*>\s*<div>ROE</div>\s*</th>(.*?)(?=</tr>)',
            html, re.DOTALL,
        )
        if roe_m:
            roe_vals = re.findall(r'<td[^>]*class="[^"]*r[^"]*"[^>]*>([\d.,-]+)</td>', roe_m.group(1))
            if roe_vals:
                result["roe"] = [_safe_float(v) for v in roe_vals]

    except Exception as e:
        logger.debug(f"[펀더멘털] FnGuide 스크래핑 오류 ({stock_code}): {e}")
    return result


def _fetch_naver_main(stock_code: str) -> dict:
    """네이버 파이낸스 메인 페이지에서 PER·PBR·EPS 스크래핑 (pykrx 실패 시 대체)."""
    result: dict = {}
    try:
        url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        html = raw.decode("euc-kr", errors="replace")

        for field, eid in (("per", "_per"), ("pbr", "_pbr"), ("eps", "_eps")):
            m = re.search(rf'<em[^>]*id="{eid}"[^>]*>([^<]+)</em>', html)
            if m:
                result[field] = _safe_float(m.group(1))
    except Exception as e:
        logger.debug(f"[펀더멘털] Naver main 오류 ({stock_code}): {e}")
    return result


# ── 점수 계산 ─────────────────────────────────────────────────────

def _growth_to_score(g: Optional[float]) -> float:
    """성장률(%) → 점수(-100 ~ +100)."""
    if g is None:
        return 0.0
    if g >= 30:  return 100.0
    if g >= 15:  return 70.0
    if g >= 5:   return 40.0
    if g >= 0:   return 15.0
    if g >= -5:  return -15.0
    if g >= -20: return -50.0
    return -100.0


def _calc_growth(current: Optional[int], prev: Optional[int]) -> Optional[float]:
    """전년 대비 성장률(%) 계산. 전년이 0이거나 없으면 None."""
    if current is None or prev is None or prev == 0:
        return None
    return round((current - prev) / abs(prev) * 100, 2)


def _calc_roe_score(roe: Optional[float]) -> float:
    if roe is None: return 0.0
    if roe >= 25:   return 100.0
    if roe >= 15:   return 75.0
    if roe >= 10:   return 50.0
    if roe >= 5:    return 25.0
    if roe >= 0:    return 0.0
    if roe >= -10:  return -50.0
    return -100.0


def _calc_debt_risk_score(debt: Optional[float]) -> float:
    """부채비율(%) → 점수 (낮을수록 안전 → 높은 점수)."""
    if debt is None: return 0.0
    if debt <= 30:   return 100.0
    if debt <= 70:   return 75.0
    if debt <= 150:  return 40.0
    if debt <= 300:  return -20.0
    return -80.0


def _calc_valuation_score(per: Optional[float], pbr: Optional[float]) -> float:
    scores: list[float] = []
    if per is not None and per > 0:
        if per <= 8:    scores.append(80.0)
        elif per <= 12: scores.append(60.0)
        elif per <= 18: scores.append(30.0)
        elif per <= 25: scores.append(0.0)
        elif per <= 40: scores.append(-40.0)
        else:           scores.append(-70.0)
    elif per is not None and per < 0:  # 적자 → 벌점
        scores.append(-80.0)

    if pbr is not None and pbr > 0:
        if pbr <= 0.8:   scores.append(80.0)
        elif pbr <= 1.5: scores.append(50.0)
        elif pbr <= 3.0: scores.append(10.0)
        elif pbr <= 5.0: scores.append(-30.0)
        else:            scores.append(-60.0)

    return round(sum(scores) / len(scores), 2) if scores else 0.0


def _calc_fundamental_score(
    rev_growth: Optional[float],
    op_growth:  Optional[float],
    net_growth: Optional[float],
    roe_sc:     float,
    debt_sc:    float,
    val_sc:     float,
) -> float:
    g_score = (
        _growth_to_score(rev_growth) * 0.30
        + _growth_to_score(op_growth)  * 0.40
        + _growth_to_score(net_growth) * 0.30
    )
    return round(g_score * 0.35 + roe_sc * 0.25 + debt_sc * 0.25 + val_sc * 0.15, 2)


def _determine_signal(score: float) -> str:
    if score >= 65:  return "매우 우량"
    if score >= 35:  return "우량"
    if score >= 5:   return "보통"
    if score >= -25: return "주의"
    return "위험"


# ── AI 해설 ───────────────────────────────────────────────────────

def _sanitize(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    for p in _BANNED:
        text = text.replace(p, "")
    return text.strip() or None


def _call_fundamental_ai(
    stock_code: str,
    stock_name: str,
    metrics: dict,
    target_date: date,
) -> dict:
    """GPT-4o-mini로 펀더멘털 AI 해설 생성."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return {}
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        def _fmt(v, unit="", na="N/A"):
            return f"{v:,.0f}{unit}" if v is not None else na

        prompt = (
            f"[기준일: {target_date}] 분석 종목: {stock_name}({stock_code})\n\n"
            f"■ 연간 재무 데이터 (억원)\n"
            f"  매출액 당해: {_fmt(metrics.get('revenue_current'))} / "
            f"전년: {_fmt(metrics.get('revenue_prev1'))} / "
            f"전전년: {_fmt(metrics.get('revenue_prev2'))}\n"
            f"  영업이익 당해: {_fmt(metrics.get('op_income_current'))} / "
            f"전년: {_fmt(metrics.get('op_income_prev1'))}\n"
            f"  당기순이익 당해: {_fmt(metrics.get('net_income_current'))} / "
            f"전년: {_fmt(metrics.get('net_income_prev1'))}\n\n"
            f"■ 성장률\n"
            f"  매출 성장률: {_fmt(metrics.get('revenue_growth'), '%')}\n"
            f"  영업이익 성장률: {_fmt(metrics.get('operating_income_growth'), '%')}\n"
            f"  순이익 성장률: {_fmt(metrics.get('net_income_growth'), '%')}\n\n"
            f"■ 수익성·안정성·밸류에이션\n"
            f"  ROE: {_fmt(metrics.get('roe'), '%')} | "
            f"부채비율: {_fmt(metrics.get('debt_ratio'), '%')} | "
            f"PER: {_fmt(metrics.get('per'), '배')} | "
            f"PBR: {_fmt(metrics.get('pbr'), '배')} | "
            f"EPS: {_fmt(metrics.get('eps'), '원')}\n\n"
            f"■ 분석 점수\n"
            f"  펀더멘털 점수: {metrics.get('fundamental_score', 0):.1f}pt "
            f"({metrics.get('fundamental_signal', '보통')})\n"
            f"  ROE 점수: {metrics.get('roe_score', 0):.0f} / "
            f"부채 안전 점수: {metrics.get('debt_risk_score', 0):.0f} / "
            f"밸류에이션 점수: {metrics.get('valuation_score', 0):.0f}\n\n"
            "위 데이터를 바탕으로 JSON 형식의 펀더멘털 해설을 작성하세요."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=600,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "ai_fundamental_summary": _sanitize(raw.get("ai_fundamental_summary")),
            "ai_growth_comment":      _sanitize(raw.get("ai_growth_comment")),
            "ai_valuation_comment":   _sanitize(raw.get("ai_valuation_comment")),
            "ai_risk_comment":        _sanitize(raw.get("ai_risk_comment")),
        }
    except Exception as e:
        logger.error(f"[펀더멘털AI] {stock_code} 오류: {e}")
        return {}


# ── DB 저장 ───────────────────────────────────────────────────────

def _upsert(session, stock_code: str, analysis_date: date, data: dict) -> None:
    fields = {k: v for k, v in data.items() if k not in ("stock_code", "analysis_date")}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(
        "INSERT INTO fundamental_analysis_results "
        "(stock_code, analysis_date, "
        + ", ".join(fields.keys())
        + ") VALUES (:stock_code, :analysis_date, "
        + ", ".join(f":{k}" for k in fields)
        + f") ON DUPLICATE KEY UPDATE {set_clause}, updated_at = NOW()"
    )
    session.execute(sql, {"stock_code": stock_code, "analysis_date": analysis_date, **fields})
    session.commit()


# ── 메인 분석 ────────────────────────────────────────────────────

def analyze_fundamental(
    stock_code: str,
    analysis_date: date,
    with_ai: bool = True,
) -> dict:
    """
    단일 종목 펀더멘털 분석 → DB 저장.

    Returns:
        {status, stock_code, stock_name, fundamental_score, fundamental_signal, ...}
    """
    session = get_db_session()
    try:
        stock = session.execute(
            select(Stock).where(Stock.stock_code == stock_code)
        ).scalar_one_or_none()
        stock_name = stock.stock_name if stock else stock_code

        # 1) pykrx: PER, PBR, EPS
        krx_data  = _fetch_pykrx_fundamental(stock_code, analysis_date)
        # 2) FnGuide: 연간 재무 데이터 (매출/영업이익/순이익/ROE/부채비율)
        fin_data  = _fetch_fnguide(stock_code)
        # 3) 네이버 메인 (pykrx 실패 시 보완)
        nav_main  = _fetch_naver_main(stock_code) if not krx_data else {}

        per = krx_data.get("per") or nav_main.get("per")
        pbr = krx_data.get("pbr") or nav_main.get("pbr")
        eps = krx_data.get("eps") or (int(nav_main["eps"]) if nav_main.get("eps") else None)

        # ROE, 부채비율 — finsum 최신값 사용
        def _latest(lst: Optional[list]) -> Optional[float]:
            """리스트의 마지막 유효값 반환 (올래된→최신 순서 가정)."""
            if not lst:
                return None
            clean = [v for v in lst if v is not None]
            return clean[-1] if clean else None

        roe        = _latest(fin_data.get("roe"))
        debt_ratio = _latest(fin_data.get("debt_ratio"))

        # 연간 재무: 처음 3개 유효값 (오래된 → 최신, FnGuide 연간 테이블 순서)
        # oldest=prev2, middle=prev1, newest=current
        def _first3_annual(lst: Optional[list]) -> tuple:
            """[2023, 2024, 2025, ...] 리스트에서 (current=최신, prev1, prev2) 반환."""
            if not lst:
                return None, None, None
            clean = [v for v in lst if v is not None]
            n = len(clean)
            # 최대 3개 연간값 사용 (분기 혼입 방지를 위해 앞 3개만)
            cur = int(clean[min(n-1, 2)]) if n >= 1 else None
            p1  = int(clean[min(n-2, 1)]) if n >= 2 else None
            p2  = int(clean[0])           if n >= 3 else None
            return cur, p1, p2

        rev_c, rev_p1, rev_p2 = _first3_annual(fin_data.get("revenue"))
        opi_c, opi_p1, opi_p2 = _first3_annual(fin_data.get("op_income"))
        net_c, net_p1, net_p2 = _first3_annual(fin_data.get("net_income"))

        # EPS 전년 비교 — finsum eps_hist 사용
        eps_hist = fin_data.get("eps_hist")
        eps_cur_f  = _latest(eps_hist)
        eps_prev_f = eps_hist[-2] if eps_hist and len(eps_hist) >= 2 else None
        eps_growth = _calc_growth(
            int(eps_cur_f) if eps_cur_f else None,
            int(eps_prev_f) if eps_prev_f else None,
        )

        # 성장률
        rev_g = _calc_growth(rev_c, rev_p1)
        opi_g = _calc_growth(opi_c, opi_p1)
        net_g = _calc_growth(net_c, net_p1)

        # 점수
        roe_sc  = _calc_roe_score(roe)
        debt_sc = _calc_debt_risk_score(debt_ratio)
        val_sc  = _calc_valuation_score(per, pbr)
        f_score = _calc_fundamental_score(rev_g, opi_g, net_g, roe_sc, debt_sc, val_sc)
        signal  = _determine_signal(f_score)

        metrics = {
            "revenue_current": rev_c, "revenue_prev1": rev_p1, "revenue_prev2": rev_p2,
            "op_income_current": opi_c, "op_income_prev1": opi_p1, "op_income_prev2": opi_p2,
            "net_income_current": net_c, "net_income_prev1": net_p1, "net_income_prev2": net_p2,
            "revenue_growth": rev_g,
            "operating_income_growth": opi_g,
            "net_income_growth": net_g,
            "eps_growth": eps_growth,
            "eps": eps, "per": per, "pbr": pbr, "roe": roe, "debt_ratio": debt_ratio,
            "roe_score": round(roe_sc, 2),
            "debt_risk_score": round(debt_sc, 2),
            "valuation_score": round(val_sc, 2),
            "fundamental_score": f_score,
            "fundamental_signal": signal,
            "data_source": "pykrx+fnguide" if krx_data else "fnguide",
        }

        # AI 해설
        if with_ai:
            ai = _call_fundamental_ai(stock_code, stock_name, metrics, analysis_date)
            metrics.update(ai)

        _upsert(session, stock_code, analysis_date, metrics)

        logger.info(
            f"[펀더멘털] {stock_code} {stock_name} "
            f"점수={f_score:.1f} 시그널={signal} "
            f"매출성장={rev_g}% 영업이익성장={opi_g}% ROE={roe}%"
        )
        return {
            "status": "success",
            "stock_code": stock_code,
            "stock_name": stock_name,
            "fundamental_score": f_score,
            "fundamental_signal": signal,
            "revenue_growth": rev_g,
            "operating_income_growth": opi_g,
            "net_income_growth": net_g,
            "roe": roe,
            "debt_ratio": debt_ratio,
            "per": per,
            "pbr": pbr,
        }
    except Exception as e:
        logger.error(f"[펀더멘털] {stock_code} 분석 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "stock_code": stock_code, "message": str(e)}
    finally:
        session.close()


# ── 배치 ─────────────────────────────────────────────────────────

def run_fundamental_batch(
    analysis_date: Optional[date] = None,
    limit: int = 80,
    delay_sec: float = 0.5,
) -> dict:
    """관심종목 + 분석점수 상위 종목 펀더멘털 배치 분석."""
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
    finally:
        session.close()

    targets = list(dict.fromkeys(list(watchlist_codes) + top_codes))[:limit]
    if not targets:
        return {"status": "no_data", "message": f"{analysis_date} 분석 대상 종목 없음"}

    success = skipped = errors = 0
    for code in targets:
        r = analyze_fundamental(code, analysis_date, with_ai=True)
        if r.get("status") == "success":
            success += 1
        elif r.get("status") == "no_data":
            skipped += 1
        else:
            errors += 1
        if delay_sec > 0:
            time.sleep(delay_sec)

    return {
        "status": "success" if errors == 0 else "partial",
        "analysis_date": str(analysis_date),
        "total": len(targets),
        "success": success,
        "skipped": skipped,
        "errors": errors,
    }


# ── DB 읽기 ───────────────────────────────────────────────────────

def _row_to_dict(row: FundamentalAnalysisResult) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    return {
        "stock_code":    row.stock_code,
        "analysis_date": str(row.analysis_date),
        # 재무 데이터
        "revenue_current":  row.revenue_current,
        "revenue_prev1":    row.revenue_prev1,
        "revenue_prev2":    row.revenue_prev2,
        "op_income_current": row.op_income_current,
        "op_income_prev1":   row.op_income_prev1,
        "net_income_current": row.net_income_current,
        "net_income_prev1":   row.net_income_prev1,
        # 성장률
        "revenue_growth":          _f(row.revenue_growth),
        "operating_income_growth": _f(row.operating_income_growth),
        "net_income_growth":       _f(row.net_income_growth),
        "eps_growth":              _f(row.eps_growth),
        # 지표
        "eps":        row.eps,
        "per":        _f(row.per),
        "pbr":        _f(row.pbr),
        "roe":        _f(row.roe),
        "debt_ratio": _f(row.debt_ratio),
        # 점수
        "roe_score":          _f(row.roe_score),
        "debt_risk_score":    _f(row.debt_risk_score),
        "valuation_score":    _f(row.valuation_score),
        "fundamental_score":  _f(row.fundamental_score),
        "fundamental_signal": row.fundamental_signal or "보통",
        # AI
        "ai_fundamental_summary": row.ai_fundamental_summary,
        "ai_growth_comment":      row.ai_growth_comment,
        "ai_valuation_comment":   row.ai_valuation_comment,
        "ai_risk_comment":        row.ai_risk_comment,
        "data_source": row.data_source,
        "updated_at":  str(row.updated_at) if row.updated_at else "-",
    }


def get_fundamental(
    stock_code: str,
    analysis_date: Optional[date] = None,
) -> Optional[dict]:
    session = get_db_session()
    try:
        q = select(FundamentalAnalysisResult).where(
            FundamentalAnalysisResult.stock_code == stock_code
        )
        if analysis_date:
            q = q.where(FundamentalAnalysisResult.analysis_date == analysis_date)
        q = q.order_by(FundamentalAnalysisResult.analysis_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        return _row_to_dict(row) if row else None
    finally:
        session.close()


def get_fundamental_top(
    analysis_date: Optional[date] = None,
    limit: int = 50,
    signal: Optional[str] = None,
) -> list[dict]:
    session = get_db_session()
    try:
        if analysis_date is None:
            latest = session.execute(
                select(FundamentalAnalysisResult.analysis_date)
                .order_by(FundamentalAnalysisResult.analysis_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest:
                return []
            analysis_date = latest

        q = select(FundamentalAnalysisResult).where(
            FundamentalAnalysisResult.analysis_date == analysis_date
        )
        if signal:
            q = q.where(FundamentalAnalysisResult.fundamental_signal == signal)
        q = q.order_by(FundamentalAnalysisResult.fundamental_score.desc()).limit(limit)
        rows = session.execute(q).scalars().all()
        return [_row_to_dict(r) for r in rows]
    finally:
        session.close()
