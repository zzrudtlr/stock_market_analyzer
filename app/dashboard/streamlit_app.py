"""
Stock Market Analyzer - Streamlit 대시보드
실행: streamlit run app/dashboard/streamlit_app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date
from sqlalchemy import select

from app.database import get_db_session, test_connection
from app.models.ai_analysis import StockAIAnalysis
from app.models.analysis import StockAnalysisResult
from app.models.disclosure_ai_analysis import DisclosureAIAnalysis
from app.models.market_report_ai import MarketReportAI
from app.models.collector_log import CollectorLog
from app.models.disclosure import Disclosure
from app.models.market import MarketIndex
from app.models.stock import Stock
from app.models.watchlist import WatchlistGroup, WatchlistItem
from app.services.analysis_service import (
    get_analysis_results,
    get_analysis_summary,
    get_high_volume_stocks,
)
from app.services.price_service import get_price_history
from app.services.report_service import get_latest_report
from app.utils.logger import setup_logger

setup_logger()

DISCLAIMER = (
    "본 분석은 가격, 거래량, 수급, 뉴스, 실적, 추세 데이터를 기반으로 생성된 참고용 시장 분석입니다.<br>"
    "투자 판단은 사용자 본인 책임입니다."
)

SIGNAL_ICON = {
    "강세 관심": "🔥",
    "추세 유지": "↗️",
    "관망": "⏸️",
    "약세 주의": "⚠️",
    "하락 위험": "🚨",
}

st.set_page_config(
    page_title="Stock Market Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* ── Sidebar Nav Buttons ── */
    [data-testid="stSidebar"] .stButton>button{
        background:transparent !important;border:none !important;
        color:var(--text-color) !important;text-align:left !important;
        padding:9px 14px !important;font-size:14px !important;
        width:100% !important;border-radius:6px !important;
        margin:1px 0 !important;transition:all .15s !important;
        box-shadow:none !important;opacity:0.65 !important;
    }
    [data-testid="stSidebar"] .stButton>button:hover{
        background:var(--secondary-background-color) !important;
        opacity:1 !important;
    }
    .nav-active{
        background:var(--secondary-background-color);
        border-left:3px solid var(--primary-color);
        color:var(--text-color);padding:9px 11px;
        border-radius:0 6px 6px 0;font-size:14px;margin:1px 0;font-weight:600;
    }
    .nav-label{
        font-size:10px;color:var(--text-color);opacity:0.45;
        text-transform:uppercase;letter-spacing:.7px;margin:12px 0 6px;font-weight:600;
    }

    /* ── KPI Cards ── */
    .kpi-card{background:var(--secondary-background-color);
              border:1px solid rgba(128,128,128,0.2);border-radius:10px;
              padding:16px 18px;overflow:hidden;margin-bottom:4px;}
    .kpi-title{font-size:11px;color:var(--text-color);opacity:0.55;
               text-transform:uppercase;letter-spacing:.7px;margin-bottom:6px;}
    .kpi-value{font-size:26px;font-weight:700;color:var(--text-color);line-height:1.2;}
    .kpi-chg{font-size:12px;margin-top:4px;}
    .kpi-up{color:#2ea043;}.kpi-dn{color:#e5534b;}.kpi-ne{color:var(--text-color);opacity:0.5;}

    /* ── Index Cards ── */
    .idx-card{background:var(--secondary-background-color);
              border:1px solid rgba(128,128,128,0.2);border-radius:10px;
              padding:14px 16px;margin-bottom:10px;}
    .idx-name{font-size:11px;color:var(--text-color);opacity:0.55;
              text-transform:uppercase;letter-spacing:.6px;font-weight:600;}
    .idx-val{font-size:22px;font-weight:700;color:var(--text-color);margin:4px 0;}
    .idx-up{font-size:12px;color:#2ea043;}.idx-dn{font-size:12px;color:#e5534b;}

    /* ── Section Header ── */
    .sec-hd{font-size:11px;color:var(--text-color);opacity:0.5;
            text-transform:uppercase;letter-spacing:.7px;margin:18px 0 8px;
            font-weight:600;border-bottom:1px solid rgba(128,128,128,0.2);padding-bottom:5px;}

    /* ── Disclosure Rows ── */
    .disc-row{padding:6px 0;border-bottom:1px solid rgba(128,128,128,0.15);
              font-size:12px;color:var(--text-color);line-height:1.5;}
    .disc-row:last-child{border-bottom:none;}
    .d-lo{color:#2ea043;}.d-me{color:#d29922;}.d-hi{color:#e5534b;}

    /* ── Disclaimer ── */
    .disclaimer{background:rgba(210,153,34,0.10);border-left:3px solid #d29922;
                padding:10px 12px;border-radius:4px;font-size:11.5px;
                color:var(--text-color);line-height:1.6;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ── 포맷 헬퍼 ─────────────────────────────────────────────────

def _fmt_return(v):
    return f"{v:+.2f}%" if v is not None else "-"

def _fmt_score(v):
    return f"{v:.1f}" if v is not None else "-"

def _fmt_ratio(v):
    return f"{v:.2f}x" if v is not None else "-"


def _sparkline_svg(values, color="#3fb950", w=90, h=32):
    """SVG 스파크라인 생성 (인라인 HTML용)."""
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return ""
    mn, mx = min(vals), max(vals)
    rng = max(mx - mn, 1e-9)
    pad = 3
    pts = " ".join(
        f"{pad + i / (len(vals)-1) * (w-2*pad):.1f},{pad + (1-(v-mn)/rng)*(h-2*pad):.1f}"
        for i, v in enumerate(vals)
    )
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def _kpi_card_html(title, value, sub="", is_up=None, svg=""):
    cls = "kpi-up" if is_up is True else "kpi-dn" if is_up is False else "kpi-ne"
    svg_html = f'<div style="float:right;margin:-2px 0 0 4px;">{svg}</div>' if svg else ""
    sub_html  = f'<div class="kpi-chg {cls}">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-card">{svg_html}'
        f'<div class="kpi-title">{title}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{sub_html}</div>'
    )


def _idx_card_html(name, close, change_rate, svg=""):
    cls   = "idx-up" if change_rate >= 0 else "idx-dn"
    arrow = "▲" if change_rate >= 0 else "▼"
    svg_html = f'<div style="margin-top:8px;">{svg}</div>' if svg else ""
    return (
        f'<div class="idx-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
        f'<span class="idx-name">{name}</span>'
        f'<span class="{cls}">{arrow} {change_rate:+.2f}%</span></div>'
        f'<div class="idx-val">{close:,.2f}</div>'
        f'{svg_html}</div>'
    )


def _build_selection_reason(item: dict, group_name: str = "") -> str:
    """그룹 특성에 따른 선정 사유 요약 텍스트를 생성합니다 (참고용)."""
    signal_reason = item.get("signal_reason") or ""
    if signal_reason:
        return signal_reason

    is_short = any(k in group_name for k in ["단기", "모멘텀", "스윙", "단타", "단기관심"])
    is_long  = any(k in group_name for k in ["장기", "중장기", "성장", "배당", "가치", "장기관심"])

    parts = []

    if is_short or (not is_long):
        r5   = item.get("return_5d")
        r20  = item.get("return_20d")
        vol5 = item.get("volume_ratio_5d")
        mom  = item.get("momentum_score") or 0
        vols = item.get("volume_score")   or 0
        risk = item.get("risk_score")     or 0

        if r5 is not None:
            parts.append(f"5일 수익률 {r5:+.1f}%")
        if r20 is not None:
            parts.append(f"20일 수익률 {r20:+.1f}%")
        if vol5 is not None and vol5 > 1.2:
            parts.append(f"거래량비율 {vol5:.1f}배")
        if mom > 5:
            parts.append(f"모멘텀점수 {mom:.0f}점")
        if vols > 5:
            parts.append(f"거래량점수 {vols:.0f}점")
        if risk >= 15:
            parts.append(f"⚠️ 위험점수 {risk:.0f}점 — 변동성 주의")

    if is_long:
        r20  = item.get("return_20d")
        r60  = item.get("return_60d")
        ma20 = item.get("ma20")
        ma60 = item.get("ma60")
        ma120= item.get("ma120")
        rs   = item.get("relative_strength")
        trend= item.get("trend_score") or 0
        risk = item.get("risk_score")  or 0

        if r20 is not None:
            parts.append(f"20일 수익률 {r20:+.1f}%")
        if r60 is not None:
            parts.append(f"60일 수익률 {r60:+.1f}%")
        if ma20 and ma60 and ma120:
            if ma20 > ma60 > ma120:
                parts.append("이동평균 상승정배열(MA20>MA60>MA120)")
            elif ma20 < ma60 < ma120:
                parts.append("이동평균 하락역배열(MA20<MA60<MA120)")
        if rs is not None:
            parts.append(f"시장대비 상대강도 {rs:+.1f}%p")
        if trend > 5:
            parts.append(f"추세점수 {trend:.0f}점")
        if risk >= 15:
            parts.append(f"⚠️ 위험점수 {risk:.0f}점 — 변동성 주의")

    signal = item.get("final_signal") or ""
    if signal:
        parts.append(f"시그널: {signal}")

    return " / ".join(parts) if parts else "분석 데이터 기반 참고용 관심 종목"


def _build_outlook_analysis(analysis: dict, latest_close) -> dict:
    """기술적 지표 기반 향후 전망 분석 데이터 생성 (참고용, 투자 권유 아님)."""
    rsi       = analysis.get("rsi14")        or 0
    vol_ratio = analysis.get("volume_ratio_5d") or 1.0
    volatility= analysis.get("volatility_20d") or 0
    rel_str   = analysis.get("relative_strength") or 0
    risk      = analysis.get("risk_score")   or 0
    r5        = analysis.get("return_5d")    or 0
    r20       = analysis.get("return_20d")   or 0
    r60       = analysis.get("return_60d")   or 0
    ma5       = analysis.get("ma5")
    ma20      = analysis.get("ma20")
    ma60      = analysis.get("ma60")
    ma120     = analysis.get("ma120")
    bullish   = analysis.get("bullish_score") or 0
    bearish   = analysis.get("bearish_score") or 0

    # ── 단기 전망 포인트 ──────────────────────────────────────
    short_pts = []
    if rsi >= 70:
        short_pts.append(f"RSI {rsi:.1f} — 과매수 구간 진입, 단기 조정 가능성 점검 필요")
    elif rsi <= 30:
        short_pts.append(f"RSI {rsi:.1f} — 과매도 구간, 기술적 반등 가능성 주목")
    elif rsi >= 60:
        short_pts.append(f"RSI {rsi:.1f} — 중립 상단, 상승 모멘텀 유지 중")
    elif rsi <= 40:
        short_pts.append(f"RSI {rsi:.1f} — 중립 하단, 하락 압력 일부 존재")
    else:
        short_pts.append(f"RSI {rsi:.1f} — 중립 구간, 방향성 확인 필요")

    if ma5 and ma20:
        if ma5 > ma20:
            short_pts.append(f"MA5({ma5:,.0f}원) > MA20({ma20:,.0f}원) — 단기 상승 기조")
        else:
            diff_pct = (ma20 - ma5) / ma20 * 100
            short_pts.append(
                f"MA5({ma5:,.0f}원) < MA20({ma20:,.0f}원) — 단기 하락 기조 "
                f"({diff_pct:.1f}% 이격, 반전 신호 확인 필요)"
            )

    if vol_ratio >= 2.5:
        short_pts.append(f"거래량 비율 {vol_ratio:.1f}배 — 평소 대비 거래 급증, 단기 변곡점 가능성 높음")
    elif vol_ratio >= 1.5:
        short_pts.append(f"거래량 비율 {vol_ratio:.1f}배 — 거래 증가 확인, 추세 강도 점검")
    else:
        short_pts.append(f"거래량 비율 {vol_ratio:.1f}배 — 거래량 평이, 눈에 띄는 변화 없음")

    if r5 >= 5:
        short_pts.append(f"5일 수익률 {r5:+.1f}% — 단기 상승 모멘텀 확인")
    elif r5 <= -5:
        short_pts.append(f"5일 수익률 {r5:+.1f}% — 단기 하락 압력, 저점 확인 필요")
    else:
        short_pts.append(f"5일 수익률 {r5:+.1f}% — 단기 변동 제한적")

    # ── 중기 전망 포인트 ──────────────────────────────────────
    mid_pts = []
    if ma20 and ma60:
        if ma20 > ma60:
            mid_pts.append(f"MA20({ma20:,.0f}원) > MA60({ma60:,.0f}원) — 중기 상승 추세 유지")
        else:
            mid_pts.append(f"MA20({ma20:,.0f}원) < MA60({ma60:,.0f}원) — 중기 하락 추세, 추세 전환 신호 대기")

    if ma60 and ma120:
        if ma60 > ma120:
            mid_pts.append(f"MA60 > MA120 — 중장기 상승 기조 형성")
        else:
            mid_pts.append(f"MA60 < MA120 — 장기 추세 약화, 중장기 저점 확인 필요")

    if rel_str >= 5:
        mid_pts.append(f"시장 대비 상대강도 {rel_str:+.1f}%p — KOSPI 대비 강세, 독립적 상승력 확인")
    elif rel_str <= -5:
        mid_pts.append(f"시장 대비 상대강도 {rel_str:+.1f}%p — KOSPI 대비 약세, 종목 고유 요인 점검 필요")
    else:
        mid_pts.append(f"시장 대비 상대강도 {rel_str:+.1f}%p — 시장과 유사한 흐름")

    if volatility >= 4:
        mid_pts.append(f"변동성(20일) {volatility:.1f}% — 고변동성 구간, 리스크 관리 중요")
    elif volatility >= 2:
        mid_pts.append(f"변동성(20일) {volatility:.1f}% — 보통 수준 변동성")
    else:
        mid_pts.append(f"변동성(20일) {volatility:.1f}% — 저변동성 안정 구간")

    if r20 >= 10:
        mid_pts.append(f"20일 수익률 {r20:+.1f}%, 60일 수익률 {r60:+.1f}% — 중기 모멘텀 양호")
    elif r20 <= -10:
        mid_pts.append(f"20일 수익률 {r20:+.1f}%, 60일 수익률 {r60:+.1f}% — 중기 하락 압력 지속")
    else:
        mid_pts.append(f"20일 수익률 {r20:+.1f}%, 60일 수익률 {r60:+.1f}%")

    # ── 지지/저항 레벨 ────────────────────────────────────────
    support, resistance = [], []
    close = float(latest_close) if latest_close else None
    for lbl, val in [("MA20", ma20), ("MA60", ma60), ("MA120", ma120)]:
        if val and close:
            if close > val:
                support.append(f"{lbl}: {val:,.0f}원")
            else:
                resistance.append(f"{lbl}: {val:,.0f}원")

    # ── 시나리오 ──────────────────────────────────────────────
    # 강세 시나리오
    bull_cond = []
    if ma5 and ma20 and ma5 > ma20:
        bull_cond.append("단기 이동평균 상승 기조 유지")
    if vol_ratio >= 1.3:
        bull_cond.append("거래량 증가세 지속")
    if rsi < 65:
        bull_cond.append("RSI 과매수 미도달")
    if rel_str > 0:
        bull_cond.append("시장 대비 상대강도 양호")
    if ma20 and ma60 and ma20 > ma60:
        bull_cond.append("중기 상승 추세 유지")

    if bullish >= 15:
        bull_outlook = (
            f"강세 점수({bullish:.0f}점)가 높고, "
            + (", ".join(bull_cond[:3]) + "." if bull_cond else "일부 긍정 지표가 확인됩니다.")
            + " 현재 조건이 유지될 경우 추가 상승 흐름 가능성에 주목할 수 있습니다."
        )
    else:
        bull_cond_txt = ", ".join(bull_cond[:2]) if bull_cond else "현재 강세 조건 미충족"
        bull_outlook = (
            f"강세 점수({bullish:.0f}점)가 아직 낮습니다. "
            + bull_cond_txt + ". 추가 확인 후 방향성 판단이 합리적입니다."
        )

    # 약세 시나리오
    bear_cond = []
    if rsi >= 65:
        bear_cond.append(f"RSI {rsi:.0f} 과매수 근접")
    if risk >= 15:
        bear_cond.append(f"위험 점수 {risk:.0f}점(고위험 구간)")
    if r5 < 0 and r20 < 0:
        bear_cond.append("단기·중기 수익률 동반 마이너스")
    if ma5 and ma20 and ma5 < ma20:
        bear_cond.append("단기 이동평균 역배열")
    if volatility >= 4:
        bear_cond.append(f"변동성 {volatility:.1f}%로 고변동성 구간")

    if bear_cond:
        bear_outlook = (
            "하락 위험 신호 점검이 필요합니다. "
            + ", ".join(bear_cond[:3]) + " 등의 신호에 주의하세요. "
            + "손실 관리 관점에서 리스크 요인을 사전에 확인하는 것이 중요합니다."
        )
    else:
        bear_outlook = (
            f"현재 주요 하락 신호는 제한적입니다(위험점수 {risk:.0f}점). "
            "그러나 시장 전반 흐름 및 외부 변수를 함께 점검하는 것이 중요합니다."
        )

    # 중립 시나리오
    gap = bullish - bearish
    if abs(gap) < 5:
        neutral_outlook = (
            f"강세({bullish:.0f}점)·약세({bearish:.0f}점) 점수가 팽팽하게 균형을 이루고 있습니다. "
            "방향성 확인 전 관망하면서 거래량 변화와 이동평균 방향을 모니터링하는 것이 합리적입니다."
        )
    elif gap > 0:
        neutral_outlook = (
            f"강세({bullish:.0f}점) > 약세({bearish:.0f}점)로 강세 우위이나, "
            "추세 지속 여부를 추가 확인한 후 판단하세요. "
            "단기 과매수 여부와 거래량 유지 여부가 핵심 확인 포인트입니다."
        )
    else:
        neutral_outlook = (
            f"약세({bearish:.0f}점) > 강세({bullish:.0f}점)로 약세 우위이나, "
            "과매도 반전 가능성도 함께 점검하세요. "
            f"RSI({rsi:.0f})와 거래량 추이를 통해 반등 신호를 확인하는 것이 좋습니다."
        )

    return {
        "short_pts":   short_pts,
        "mid_pts":     mid_pts,
        "support":     support,
        "resistance":  resistance,
        "bull_outlook":  bull_outlook,
        "bear_outlook":  bear_outlook,
        "neutral_outlook": neutral_outlook,
    }


# ── 캐시 함수들 ───────────────────────────────────────────────

@st.cache_data(ttl=300)
def cached_summary(analysis_date, market=None):
    return get_analysis_summary(analysis_date, market=market)


@st.cache_data(ttl=300)
def cached_bullish(analysis_date, market=None, limit=20):
    return get_analysis_results(analysis_date, order_by="bullish_score", limit=limit, market=market)


@st.cache_data(ttl=300)
def cached_bearish(analysis_date, market=None, limit=20):
    return get_analysis_results(analysis_date, order_by="bearish_score", limit=limit, market=market)


@st.cache_data(ttl=300)
def cached_high_volume(analysis_date, market=None, limit=20):
    return get_high_volume_stocks(analysis_date, market=market, min_ratio=2.0, limit=limit)


@st.cache_data(ttl=300)
def cached_disclosures(target_date):
    session = get_db_session()
    try:
        q = (
            select(Disclosure)
            .where(Disclosure.report_date == target_date)
            .order_by(Disclosure.id.desc())
            .limit(30)
        )
        rows = session.execute(q).scalars().all()
        return [
            {
                "stock_code": r.stock_code or "-",
                "title": r.title,
                "disclosure_type": r.disclosure_type or "-",
                "risk_level": r.risk_level or "-",
                "url": r.url,
            }
            for r in rows
        ]
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_market_indices():
    session = get_db_session()
    try:
        rows = []
        for index_code, name in [("KS11", "KOSPI"), ("KQ11", "KOSDAQ")]:
            q = (
                select(MarketIndex)
                .where(MarketIndex.index_code == index_code)
                .order_by(MarketIndex.trade_date.desc())
                .limit(1)
            )
            row = session.execute(q).scalar_one_or_none()
            if row:
                rows.append({
                    "name": name,
                    "close": float(row.close_value) if row.close_value else 0,
                    "change_rate": float(row.change_rate) if row.change_rate else 0,
                    "trade_date": str(row.trade_date),
                })
        return rows
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_market_indices_history(days: int = 30):
    """KOSPI/KOSDAQ 최근 N일 종가·거래대금 이력 (스파크라인용)."""
    session = get_db_session()
    try:
        result = {}
        for code, name in [("KS11", "KOSPI"), ("KQ11", "KOSDAQ")]:
            rows = session.execute(
                select(MarketIndex.close_value, MarketIndex.trading_value)
                .where(MarketIndex.index_code == code)
                .order_by(MarketIndex.trade_date.desc())
                .limit(days)
            ).all()
            rows = list(reversed(rows))
            result[name] = {
                "closes":         [float(r.close_value)   for r in rows if r.close_value],
                "trading_values": [float(r.trading_value) for r in rows if r.trading_value],
            }
        return result
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_sector_analysis(analysis_date, market=None):
    """업종별 평균 일간 수익률 집계."""
    session = get_db_session()
    try:
        from sqlalchemy import func as _sf
        q = (
            select(
                Stock.sector,
                _sf.avg(StockAnalysisResult.daily_return).label("avg_return"),
                _sf.count(StockAnalysisResult.stock_code).label("cnt"),
            )
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code)
            .where(
                StockAnalysisResult.analysis_date == analysis_date,
                Stock.sector.isnot(None),
                Stock.sector != "",
            )
        )
        if market:
            q = q.where(Stock.market == market)
        q = q.group_by(Stock.sector).having(_sf.count(StockAnalysisResult.stock_code) >= 3)
        rows = session.execute(q).all()
        return [
            {"sector": r.sector, "avg_return": float(r.avg_return or 0), "count": r.cnt}
            for r in rows
            if r.sector
        ]
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_stock_search(keyword: str):
    session = get_db_session()
    try:
        q = (
            select(Stock)
            .where(
                (Stock.stock_code.like(f"%{keyword}%")) |
                (Stock.stock_name.like(f"%{keyword}%"))
            )
            .limit(30)
        )
        rows = session.execute(q).scalars().all()
        return [
            {"stock_code": r.stock_code, "stock_name": r.stock_name, "market": r.market, "sector": r.sector}
            for r in rows
        ]
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_stock_analysis(stock_code: str, analysis_date):
    session = get_db_session()
    try:
        q = select(StockAnalysisResult).where(
            StockAnalysisResult.stock_code == stock_code,
            StockAnalysisResult.analysis_date == analysis_date,
        ).order_by(StockAnalysisResult.id.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        if not row:
            return None
        def _f(v): return float(v) if v is not None else None
        return {
            "daily_return":      _f(row.daily_return),
            "return_5d":         _f(row.return_5d),
            "return_20d":        _f(row.return_20d),
            "return_60d":        _f(row.return_60d),
            "volume_ratio_5d":   _f(row.volume_ratio_5d),
            "volume_ratio_20d":  _f(row.volume_ratio_20d),
            "ma5":               _f(row.ma5),
            "ma20":              _f(row.ma20),
            "ma60":              _f(row.ma60),
            "ma120":             _f(row.ma120),
            "rsi14":             _f(row.rsi14),
            "volatility_20d":    _f(row.volatility_20d),
            "relative_strength": _f(row.relative_strength),
            "momentum_score":    _f(row.momentum_score),
            "volume_score":      _f(row.volume_score),
            "trend_score":       _f(row.trend_score),
            "risk_score":        _f(row.risk_score),
            "disclosure_score":  _f(row.disclosure_score),
            "bullish_score":     _f(row.bullish_score),
            "bearish_score":     _f(row.bearish_score),
            "final_signal":      row.final_signal,
            "signal_reason":     row.signal_reason,
        }
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_price_history(stock_code, days=90):
    return get_price_history(stock_code, days=days)


@st.cache_data(ttl=300)
def cached_watchlist(analysis_date):
    session = get_db_session()
    try:
        groups = session.execute(
            select(WatchlistGroup).order_by(WatchlistGroup.id)
        ).scalars().all()
        result = []
        for g in groups:
            items_rows = session.execute(
                select(WatchlistItem, Stock.stock_name, Stock.market)
                .join(Stock, WatchlistItem.stock_code == Stock.stock_code, isouter=True)
                .where(WatchlistItem.group_id == g.id)
            ).all()
            group_items = []
            for row in items_rows:
                a = session.execute(
                    select(StockAnalysisResult).where(
                        StockAnalysisResult.stock_code == row.WatchlistItem.stock_code,
                        StockAnalysisResult.analysis_date == analysis_date,
                    ).order_by(StockAnalysisResult.id.desc()).limit(1)
                ).scalar_one_or_none()
                def _af(a, col):
                    v = getattr(a, col, None)
                    return float(v) if v is not None else None
            group_items.append({
                    "stock_code":        row.WatchlistItem.stock_code,
                    "stock_name":        row.stock_name or "-",
                    "market":            row.market or "-",
                    "memo":              row.WatchlistItem.memo or "",
                    "final_signal":      a.final_signal if a else None,
                    "signal_reason":     a.signal_reason if a else None,
                    "bullish_score":     _af(a, "bullish_score")  if a else None,
                    "daily_return":      _af(a, "daily_return")   if a else None,
                    "return_5d":         _af(a, "return_5d")      if a else None,
                    "return_20d":        _af(a, "return_20d")     if a else None,
                    "return_60d":        _af(a, "return_60d")     if a else None,
                    "volume_ratio_5d":   _af(a, "volume_ratio_5d") if a else None,
                    "momentum_score":    _af(a, "momentum_score") if a else None,
                    "volume_score":      _af(a, "volume_score")   if a else None,
                    "trend_score":       _af(a, "trend_score")    if a else None,
                    "risk_score":        _af(a, "risk_score")     if a else None,
                    "rsi14":             _af(a, "rsi14")          if a else None,
                    "ma20":              _af(a, "ma20")           if a else None,
                    "ma60":              _af(a, "ma60")           if a else None,
                    "ma120":             _af(a, "ma120")          if a else None,
                    "relative_strength": _af(a, "relative_strength") if a else None,
                })
            result.append({
                "group_name":  g.group_name,
                "description": g.description or "",
                "items":       group_items,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=3600)
def cached_ai_analysis(stock_code: str, analysis_date):
    session = get_db_session()
    try:
        from sqlalchemy import and_
        q = select(StockAIAnalysis).where(
            and_(
                StockAIAnalysis.stock_code    == stock_code,
                StockAIAnalysis.analysis_date == analysis_date,
            )
        ).order_by(StockAIAnalysis.id.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        if not row:
            return None
        return {
            "ai_summary":        row.ai_summary,
            "ai_trend_comment":  row.ai_trend_comment,
            "ai_risk_comment":   row.ai_risk_comment,
            "ai_volume_comment": row.ai_volume_comment,
            "ai_signal_comment": row.ai_signal_comment,
            "updated_at": str(row.updated_at)[:19] if row.updated_at else "-",
        }
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_stock_disclosures(stock_code: str, limit: int = 10):
    """종목의 최근 공시 목록 조회."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(Disclosure)
            .where(Disclosure.stock_code == stock_code)
            .order_by(Disclosure.report_date.desc(), Disclosure.id.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "id":              r.id,
                "report_date":     str(r.report_date),
                "title":           r.title,
                "disclosure_type": r.disclosure_type or "-",
                "risk_level":      r.risk_level or "-",
                "summary":         r.summary or "",
                "url":             r.url or "",
            }
            for r in rows
        ]
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_disclosure_ai(stock_code: str, limit: int = 10):
    """종목의 저장된 공시 AI 분석 결과 조회."""
    from app.services.disclosure_ai_service import get_disclosure_analysis
    return get_disclosure_analysis(stock_code, limit=limit)


@st.cache_data(ttl=600)
def cached_market_report_ai(report_date):
    """저장된 AI 시장 리포트 조회."""
    from app.services.market_report_ai_service import get_market_report
    return get_market_report(report_date)


@st.cache_data(ttl=300)
def cached_watchlist_ai(analysis_date):
    """관심 종목별 AI 분석 데이터 조회."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(WatchlistItem, WatchlistGroup.group_name, Stock.stock_name)
            .join(WatchlistGroup, WatchlistItem.group_id == WatchlistGroup.id)
            .join(Stock, WatchlistItem.stock_code == Stock.stock_code, isouter=True)
        ).all()
        result = []
        for item, group_name, stock_name in rows:
            code = item.stock_code
            ai = session.execute(
                select(StockAIAnalysis).where(
                    StockAIAnalysis.stock_code == code,
                    StockAIAnalysis.analysis_date == analysis_date,
                ).order_by(StockAIAnalysis.id.desc()).limit(1)
            ).scalar_one_or_none()
            ar = session.execute(
                select(StockAnalysisResult).where(
                    StockAnalysisResult.stock_code == code,
                    StockAnalysisResult.analysis_date == analysis_date,
                ).order_by(StockAnalysisResult.id.desc()).limit(1)
            ).scalar_one_or_none()
            def _f(v): return float(v) if v is not None else None
            result.append({
                "stock_code":        code,
                "stock_name":        stock_name or code,
                "group_name":        group_name,
                "final_signal":      ar.final_signal if ar else None,
                "daily_return":      _f(ar.daily_return) if ar else None,
                "risk_score":        _f(ar.risk_score) if ar else None,
                "bullish_score":     _f(ar.bullish_score) if ar else None,
                "has_ai":            ai is not None,
                "ai_summary":        ai.ai_summary if ai else None,
                "ai_trend_comment":  ai.ai_trend_comment if ai else None,
                "ai_signal_comment": ai.ai_signal_comment if ai else None,
                "ai_risk_comment":   ai.ai_risk_comment if ai else None,
                "ai_volume_comment": ai.ai_volume_comment if ai else None,
                "ai_updated_at":     str(ai.updated_at)[:16] if ai and ai.updated_at else None,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_risk_stocks_ai(analysis_date, limit=15):
    """위험 점수 높은 종목 + AI 분석."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(StockAnalysisResult, Stock.stock_name)
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            .where(
                StockAnalysisResult.analysis_date == analysis_date,
                StockAnalysisResult.risk_score >= 15,
            )
            .order_by(StockAnalysisResult.risk_score.desc())
            .limit(limit)
        ).all()
        result = []
        for ar, name in rows:
            ai = session.execute(
                select(StockAIAnalysis).where(
                    StockAIAnalysis.stock_code == ar.stock_code,
                    StockAIAnalysis.analysis_date == analysis_date,
                ).order_by(StockAIAnalysis.id.desc()).limit(1)
            ).scalar_one_or_none()
            result.append({
                "stock_code":     ar.stock_code,
                "stock_name":     name or ar.stock_code,
                "final_signal":   ar.final_signal,
                "risk_score":     float(ar.risk_score)      if ar.risk_score      else 0,
                "volatility_20d": float(ar.volatility_20d)  if ar.volatility_20d  else None,
                "bearish_score":  float(ar.bearish_score)   if ar.bearish_score   else None,
                "daily_return":   float(ar.daily_return)    if ar.daily_return    else None,
                "has_ai":         ai is not None,
                "ai_risk_comment": ai.ai_risk_comment if ai else None,
                "ai_summary":      ai.ai_summary      if ai else None,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=600)
def cached_all_disclosure_ai(limit=30):
    """최근 공시 AI 분석 전체 (종목 무관)."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(DisclosureAIAnalysis, Disclosure)
            .join(Disclosure, DisclosureAIAnalysis.disclosure_id == Disclosure.id)
            .order_by(Disclosure.report_date.desc(), DisclosureAIAnalysis.id.desc())
            .limit(limit)
        ).all()
        seen, result = set(), []
        for ai_row, disc in rows:
            if disc.id in seen:
                continue
            seen.add(disc.id)
            result.append({
                "stock_code":            disc.stock_code or "-",
                "report_date":           str(disc.report_date),
                "title":                 disc.title,
                "disclosure_type":       disc.disclosure_type or "-",
                "ai_disclosure_summary": ai_row.ai_disclosure_summary,
                "ai_disclosure_risk":    ai_row.ai_disclosure_risk,
                "ai_market_impact":      ai_row.ai_market_impact,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_volume_stocks_ai(analysis_date, limit=15):
    """거래량 급증 종목 + AI 분석."""
    session = get_db_session()
    try:
        rows = session.execute(
            select(StockAnalysisResult, Stock.stock_name)
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            .where(
                StockAnalysisResult.analysis_date == analysis_date,
                StockAnalysisResult.volume_ratio_5d >= 2.0,
            )
            .order_by(StockAnalysisResult.volume_ratio_5d.desc())
            .limit(limit)
        ).all()
        result = []
        for ar, name in rows:
            ai = session.execute(
                select(StockAIAnalysis).where(
                    StockAIAnalysis.stock_code == ar.stock_code,
                    StockAIAnalysis.analysis_date == analysis_date,
                ).order_by(StockAIAnalysis.id.desc()).limit(1)
            ).scalar_one_or_none()
            result.append({
                "stock_code":       ar.stock_code,
                "stock_name":       name or ar.stock_code,
                "final_signal":     ar.final_signal,
                "volume_ratio_5d":  float(ar.volume_ratio_5d)  if ar.volume_ratio_5d  else 0,
                "volume_ratio_20d": float(ar.volume_ratio_20d) if ar.volume_ratio_20d else None,
                "daily_return":     float(ar.daily_return)     if ar.daily_return     else None,
                "has_ai":           ai is not None,
                "ai_volume_comment": ai.ai_volume_comment if ai else None,
                "ai_summary":        ai.ai_summary        if ai else None,
            })
        return result
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_theme_analysis(report_date):
    from app.services.theme_analysis_service import get_theme_analysis
    return get_theme_analysis(report_date)


@st.cache_data(ttl=300)
def cached_supply_demand_top(analysis_date, limit=30):
    from app.services.supply_demand_analysis_service import get_supply_demand_top
    return get_supply_demand_top(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=60)
def cached_supply_demand_stock(stock_code, analysis_date):
    from app.services.supply_demand_analysis_service import get_supply_demand
    return get_supply_demand(stock_code, analysis_date)


@st.cache_data(ttl=300)
def cached_news_top(analysis_date, limit=50):
    from app.services.news_analysis_service import get_news_sentiment_top
    return get_news_sentiment_top(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=60)
def cached_news_stock(stock_code, analysis_date):
    from app.services.news_analysis_service import get_news_sentiment
    return get_news_sentiment(stock_code, analysis_date)


@st.cache_data(ttl=300)
def cached_fundamental_top(analysis_date, limit=50):
    from app.services.fundamental_analysis_service import get_fundamental_top
    return get_fundamental_top(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=60)
def cached_fundamental_stock(stock_code, analysis_date):
    from app.services.fundamental_analysis_service import get_fundamental
    return get_fundamental(stock_code, analysis_date)


@st.cache_data(ttl=300)
def cached_market_flow_supply(analysis_date, limit=10):
    from app.services.supply_demand_analysis_service import get_supply_demand_top
    return get_supply_demand_top(analysis_date=analysis_date, limit=limit * 3)


@st.cache_data(ttl=300)
def cached_market_flow_news(analysis_date, limit=30):
    from app.services.news_analysis_service import get_news_sentiment_top
    return get_news_sentiment_top(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=300)
def cached_market_flow_leaders(analysis_date, limit=10):
    from app.services.market_leader_analysis_service import get_market_leaders
    return get_market_leaders(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=300)
def cached_market_flow_trading_value(analysis_date, limit=10):
    from app.services.market_leader_analysis_service import get_market_leaders_by_trading_value
    return get_market_leaders_by_trading_value(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=300)
def cached_market_flow_rotation(analysis_date):
    from app.services.theme_rotation_analysis_service import get_theme_rotation_summary, get_theme_rotation_results
    summary = get_theme_rotation_summary(analysis_date=analysis_date)
    results = get_theme_rotation_results(analysis_date=analysis_date, limit=20)
    return summary, results


@st.cache_data(ttl=300)
def cached_market_flow_risk(analysis_date, limit=10):
    from app.services.risk_analysis_service import get_risk_top
    return get_risk_top(analysis_date=analysis_date, limit=limit, sort_by="total")


@st.cache_data(ttl=300)
def cached_market_flow_chart(analysis_date, limit=10):
    from app.services.chart_pattern_analysis_service import get_chart_pattern_top
    return get_chart_pattern_top(analysis_date=analysis_date, limit=limit)


@st.cache_data(ttl=300)
def cached_advanced_market_ai(report_date):
    from app.services.advanced_market_ai_service import get_advanced_market_ai
    return get_advanced_market_ai(report_date)


@st.cache_data(ttl=300)
def cached_market_flow_foreign_top(analysis_date, limit=10):
    from app.models.supply_demand_analysis import SupplyDemandAnalysis
    session = get_db_session()
    try:
        rows = session.execute(
            select(SupplyDemandAnalysis)
            .where(SupplyDemandAnalysis.analysis_date == analysis_date)
            .order_by(SupplyDemandAnalysis.foreign_net_buy.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "stock_code":         r.stock_code,
                "foreign_net_buy":    float(r.foreign_net_buy    or 0),
                "foreign_net_buy_5d": float(r.foreign_net_buy_5d or 0),
                "foreign_buy_streak": r.foreign_buy_streak        or 0,
                "supply_signal":      r.supply_signal             or "혼조",
            }
            for r in rows
        ]
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_market_flow_institution_top(analysis_date, limit=10):
    from app.models.supply_demand_analysis import SupplyDemandAnalysis
    session = get_db_session()
    try:
        rows = session.execute(
            select(SupplyDemandAnalysis)
            .where(SupplyDemandAnalysis.analysis_date == analysis_date)
            .order_by(SupplyDemandAnalysis.institution_net_buy.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "stock_code":              r.stock_code,
                "institution_net_buy":     float(r.institution_net_buy     or 0),
                "institution_net_buy_5d":  float(r.institution_net_buy_5d  or 0),
                "institution_buy_streak":  r.institution_buy_streak          or 0,
                "supply_signal":           r.supply_signal                   or "혼조",
            }
            for r in rows
        ]
    finally:
        session.close()


@st.cache_data(ttl=300)
def cached_market_flow_news_negative(analysis_date, limit=10):
    from app.models.news_sentiment_result import NewsSentimentResult
    session = get_db_session()
    try:
        rows = session.execute(
            select(NewsSentimentResult)
            .where(
                NewsSentimentResult.analysis_date == analysis_date,
                NewsSentimentResult.news_sentiment_signal.in_(["강한 악재", "악재 우세"]),
            )
            .order_by(NewsSentimentResult.news_sentiment_score.asc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "stock_code":            r.stock_code,
                "news_sentiment_score":  float(r.news_sentiment_score  or 0),
                "news_sentiment_signal": r.news_sentiment_signal        or "중립",
                "total_news_count":      r.total_news_count             or 0,
                "negative_news_count":   r.negative_news_count          or 0,
            }
            for r in rows
        ]
    finally:
        session.close()


# ── 사이드바 ──────────────────────────────────────────────────

_PAGES = [
    "🏠 대시보드",
    "🌊 시장 종합 흐름",
    "📈 테마 분석",
    "💰 수급 분석",
    "📰 뉴스 감성",
    "📊 실적 분석",
    "⭐ 관심 종목",
    "🔍 종목 검색",
    "🤖 AI 분석",
    "📋 최신 리포트",
    "⚙️ 스케줄러",
]


def render_sidebar():
    if "page" not in st.session_state:
        st.session_state.page = _PAGES[0]

    with st.sidebar:
        st.markdown("### 📊 Stock Analyzer")
        st.markdown("---")

        analysis_date = st.date_input(
            "날짜",
            value=date.today(),
            max_value=date.today(),
        )
        market_option = st.selectbox("시장", ["전체", "KOSPI", "KOSDAQ"])
        market_filter = None if market_option == "전체" else market_option

        st.markdown("---")
        st.markdown('<p class="nav-label">메뉴</p>', unsafe_allow_html=True)

        for p in _PAGES:
            if st.session_state.page == p:
                st.markdown(f'<div class="nav-active">{p}</div>', unsafe_allow_html=True)
            else:
                if st.button(p, use_container_width=True, key=f"nav_{p}"):
                    st.session_state.page = p
                    st.rerun()

        st.markdown("---")
        st.markdown('<p class="nav-label">전체 분석</p>', unsafe_allow_html=True)
        if st.button("⬇️ 처음부터 전체 실행", use_container_width=True, key="sidebar_run_full",
                     help="종목수집→시세수집→기본분석→수급→테마→뉴스→실적→AI 전체 실행"):
            st.session_state["run_all_pending"] = True
            st.session_state["run_all_include_collect"] = True
            st.session_state["run_all_date"] = analysis_date
        if st.button("▶ 분석만 재실행", use_container_width=True, key="sidebar_run_all",
                     help="수급·테마·뉴스·실적·AI 리포트만 재실행 (데이터 이미 있을 때)"):
            st.session_state["run_all_pending"] = True
            st.session_state["run_all_include_collect"] = False
            st.session_state["run_all_date"] = analysis_date

        st.markdown("---")
        st.markdown(f'<div class="disclaimer">{DISCLAIMER}</div>', unsafe_allow_html=True)

    return st.session_state.page, analysis_date, market_filter


# ── 시장 요약 (홈) ────────────────────────────────────────────

def _run_all_analyses(analysis_date: date, include_collect: bool = False):
    """홈 대시보드 전체 분석 일괄 실행.

    include_collect=True 이면 종목수집 → 시세수집 → 기본분석까지 포함해 처음부터 실행.
    수급·테마·뉴스·실적 4개 배치는 병렬 실행하며, 이미 당일 분석된 종목은 자동 스킵합니다.
    """
    import concurrent.futures

    from app.services.supply_demand_analysis_service import run_supply_demand_batch
    from app.services.theme_analysis_service import run_theme_analysis
    from app.services.news_analysis_service import run_news_batch
    from app.services.fundamental_analysis_service import run_fundamental_batch
    from app.services.market_report_ai_service import generate_market_report
    from app.services.analysis_service import run_analysis

    results = {}
    progress_bar = st.progress(0)
    status_box   = st.empty()

    # ── 1단계: 수집 (순차) ────────────────────────────────────────
    collect_steps = []
    if include_collect:
        from app.collectors.finance_data_reader_collector import (
            collect_stock_list,
            collect_market_indices,
            collect_prices_bulk_fdr,
        )
        collect_steps = [
            ("collect_stocks",  "📋 종목 수집",            collect_stock_list),
            ("collect_indices", "📉 시장 지수 수집",        lambda: collect_market_indices(60)),
            ("collect_prices",  "📈 시세 수집 FDR (60일)", lambda: collect_prices_bulk_fdr(60)),
            ("base_analysis",   "🔬 기본 분석 실행",        lambda: run_analysis(analysis_date)),
        ]

    # 전체 진행 단계: 수집(n) + 병렬배치(1) + AI리포트(1)
    total_steps = len(collect_steps) + 2

    for i, (key, label, fn) in enumerate(collect_steps):
        status_box.info(f"[{i+1}/{total_steps}] {label} 실행 중...")
        try:
            res = fn()
            results[key] = res if isinstance(res, dict) else {"status": "success"}
        except Exception as e:
            results[key] = {"status": "error", "message": str(e)}
        progress_bar.progress((i + 1) / total_steps)

    # ── 2단계: 수급·테마·뉴스·실적 병렬 실행 ──────────────────────
    parallel_step_idx = len(collect_steps) + 1
    status_box.info(
        f"[{parallel_step_idx}/{total_steps}] "
        "💰 수급 / 📈 테마 / 📰 뉴스 / 📊 실적 병렬 분석 중..."
    )

    parallel_tasks = {
        "supply":      lambda: run_supply_demand_batch(analysis_date, limit=80),
        "theme":       lambda: run_theme_analysis(analysis_date),
        "news":        lambda: run_news_batch(analysis_date, limit=80),
        "fundamental": lambda: run_fundamental_batch(analysis_date, limit=80),
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {key: executor.submit(fn) for key, fn in parallel_tasks.items()}
        for key, future in futures.items():
            try:
                res = future.result()
                results[key] = res if isinstance(res, dict) else {"status": "success"}
            except Exception as e:
                results[key] = {"status": "error", "message": str(e)}

    progress_bar.progress(parallel_step_idx / total_steps)

    # ── 3단계: AI 리포트 (순차, 위 결과 활용) ─────────────────────
    status_box.info(f"[{total_steps}/{total_steps}] 🤖 AI 시장 리포트 생성 중...")
    try:
        res = generate_market_report(analysis_date)
        results["ai_report"] = res if isinstance(res, dict) else {"status": "success"}
    except Exception as e:
        results["ai_report"] = {"status": "error", "message": str(e)}

    progress_bar.progress(1.0)
    status_box.empty()
    progress_bar.empty()
    return results


def render_home(analysis_date: date, market):
    market_label = market or "전체"
    st.title(f"📊 시장 요약  |  {analysis_date}  |  {market_label}")

    if not test_connection():
        st.error("MySQL 연결 실패. .env 파일을 확인하세요.")
        return

    summary = cached_summary(analysis_date, market)
    total   = summary.get("total", 0)

    # ── 전체 분석 실행 패널 ───────────────────────────────────
    with st.expander("🚀 전체 분석 한 번에 실행", expanded=total == 0):
        # 데이터 없으면 자동으로 열어서 안내
        if total == 0:
            st.warning(
                f"**{analysis_date}** 분석 데이터가 없습니다. "
                "아래 **처음부터 전체 실행** 버튼으로 데이터 수집부터 모든 분석을 자동 실행하세요."
            )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**처음부터 전체 실행** *(데이터 없을 때)*")
            st.caption("① 종목수집 → ② 지수수집 → ③ 시세수집(60일) → ④ 기본분석 → ⑤ 수급 → ⑥ 테마 → ⑦ 뉴스 → ⑧ 실적 → ⑨ AI리포트")
            run_full = st.button(
                "⬇️ 처음부터 전체 실행 (약 10~15분)",
                type="primary",
                use_container_width=True,
                key="home_run_full",
            )
        with c2:
            st.markdown("**분석만 재실행** *(데이터 이미 있을 때)*")
            st.caption("⑤ 수급 → ⑥ 테마 → ⑦ 뉴스 → ⑧ 실적 → ⑨ AI리포트만 재실행")
            run_all = st.button(
                "▶ 분석만 재실행 (약 1~5분)",
                use_container_width=True,
                key="home_run_all",
            )

        triggered = run_full or run_all
        if triggered:
            results = _run_all_analyses(analysis_date, include_collect=run_full)

            label_map = {
                "collect_stocks":  "📋 종목수집",
                "collect_indices": "📉 지수수집",
                "collect_prices":  "📈 시세수집",
                "base_analysis":   "🔬 기본분석",
                "supply":          "💰 수급",
                "theme":           "📈 테마",
                "news":            "📰 뉴스",
                "fundamental":     "📊 실적",
                "ai_report":       "🤖 AI",
            }
            ok_parts, fail_parts = [], []
            for key, label in label_map.items():
                res = results.get(key)
                if res is None:
                    continue
                status = res.get("status", "error")
                if status in ("success", "partial"):
                    cnt = res.get("success", res.get("themes", res.get("count", "")))
                    ok_parts.append(f"{label} ✅" + (f" {cnt}건" if cnt else ""))
                else:
                    msg = res.get("message", "오류")[:30]
                    fail_parts.append(f"{label} ❌ ({msg})")

            if ok_parts:
                st.success("완료: " + "  |  ".join(ok_parts))
            if fail_parts:
                st.warning("실패: " + "  |  ".join(fail_parts))

            st.cache_data.clear()
            st.rerun()

    high_vol    = cached_high_volume(analysis_date, market, limit=20)
    disclosures = cached_disclosures(analysis_date)
    indices     = cached_market_indices()
    idx_hist    = cached_market_indices_history(days=30)

    bullish_cnt    = summary.get("강세 관심", 0)
    bearish_cnt    = summary.get("하락 위험", 0) + summary.get("약세 주의", 0)
    high_vol_cnt   = len(high_vol)
    disclosure_cnt = len(disclosures)

    RISK_CLS = {"주의": "d-hi", "높음": "d-hi", "보통": "d-me", "낮음": "d-lo"}

    # ── 2컬럼 레이아웃 ────────────────────────────────────────
    left_col, right_col = st.columns([7, 3])

    # ── 오른쪽 사이드: 시장 지수 카드 + 도넛 + 공시 ─────────────
    with right_col:
        st.markdown('<p class="sec-hd">시장 지수</p>', unsafe_allow_html=True)
        for idx in indices:
            name  = idx["name"]
            hist  = idx_hist.get(name, {})
            svg_c = "#3fb950" if idx["change_rate"] >= 0 else "#f85149"
            svg   = _sparkline_svg(hist.get("closes", []), color=svg_c, w=100, h=36)
            st.markdown(_idx_card_html(name, idx["close"], idx["change_rate"], svg), unsafe_allow_html=True)
        if not indices:
            st.caption("지수 없음 — `POST /api/collect/indices` 실행 필요")

        # 거래대금 도넛
        kospi_tv  = (idx_hist.get("KOSPI",  {}).get("trading_values") or [0])[-1]
        kosdaq_tv = (idx_hist.get("KOSDAQ", {}).get("trading_values") or [0])[-1]
        if kospi_tv or kosdaq_tv:
            st.markdown('<p class="sec-hd">거래대금 비중</p>', unsafe_allow_html=True)
            fig_d = go.Figure(go.Pie(
                labels=["KOSPI", "KOSDAQ"],
                values=[kospi_tv, kosdaq_tv],
                hole=0.58,
                marker_colors=["#388bfd", "#3fb950"],
                textinfo="label+percent",
                textfont=dict(size=11, color="#e6edf3"),
            ))
            fig_d.update_layout(
                height=170, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#e6edf3"), showlegend=False,
            )
            st.plotly_chart(fig_d, use_container_width=True, key="home_donut")

        # 공시 목록
        st.markdown('<p class="sec-hd">오늘의 공시</p>', unsafe_allow_html=True)
        if not disclosures:
            st.caption("오늘 공시 없음")
        else:
            disc_html = "".join(
                f'<div class="disc-row">'
                f'<span class="{RISK_CLS.get(d.get("risk_level","보통"),"d-me")}">●</span> '
                f'{d["stock_code"]} — {(d["title"][:36]+"…") if len(d.get("title",""))>36 else d.get("title","-")}'
                f'</div>'
                for d in disclosures[:12]
            )
            st.markdown(disc_html, unsafe_allow_html=True)
            if len(disclosures) > 12:
                st.caption(f"외 {len(disclosures)-12}건")

    # ── 왼쪽 메인 ────────────────────────────────────────────
    with left_col:
        # KPI 카드 4개
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                _kpi_card_html("강세 종목", f"{bullish_cnt}개", f"전체 {total}개 중", is_up=True),
                unsafe_allow_html=True,
            )
        with k2:
            st.markdown(
                _kpi_card_html("약세 종목", f"{bearish_cnt}개", "약세+하락 합산", is_up=False),
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                _kpi_card_html("거래량 급증", f"{high_vol_cnt}개", "5일 평균 2배↑"),
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                _kpi_card_html("공시 이슈", f"{disclosure_cnt}건", "오늘 등록 공시"),
                unsafe_allow_html=True,
            )

        if total == 0:
            st.warning(
                f"**{analysis_date}** 분석 데이터가 없습니다.\n\n"
                "순서대로 실행하세요:\n"
                "1. `POST /api/collect/stocks` — 종목 수집\n"
                "2. `POST /api/collect/prices/bulk?days=60` — 시세 수집\n"
                "3. `POST /api/analysis/run` — 분석 실행"
            )
        else:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            # AI 시장 요약 + 업종 차트
            sum_col, sec_col = st.columns([4, 6])

            with sum_col:
                st.markdown('<p class="sec-hd">AI 시장 요약</p>', unsafe_allow_html=True)
                from app.config import settings as _cfg_mr
                _ai_on = bool(getattr(_cfg_mr, "OPENAI_API_KEY", ""))
                if not _ai_on:
                    st.markdown(
                        '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                        'padding:14px;font-size:12px;color:#8b949e;">OPENAI_API_KEY 미설정</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    mr = cached_market_report_ai(analysis_date)
                    if mr and mr.get("market_ai_summary"):
                        st.markdown(
                            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                            f'padding:13px;font-size:12px;color:#c9d1d9;line-height:1.6;">'
                            f'{mr["market_ai_summary"]}</div>',
                            unsafe_allow_html=True,
                        )
                        if mr.get("bullish_market_comment"):
                            st.markdown(
                                f'<div style="background:#0d2818;border-left:3px solid #3fb950;'
                                f'padding:7px 11px;margin-top:7px;font-size:11px;color:#3fb950;'
                                f'border-radius:0 4px 4px 0;">'
                                f'🔥 {mr["bullish_market_comment"][:110]}</div>',
                                unsafe_allow_html=True,
                            )
                        if mr.get("bearish_market_comment"):
                            st.markdown(
                                f'<div style="background:#2d1b1b;border-left:3px solid #f85149;'
                                f'padding:7px 11px;margin-top:5px;font-size:11px;color:#f85149;'
                                f'border-radius:0 4px 4px 0;">'
                                f'📉 {mr["bearish_market_comment"][:110]}</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.markdown(
                            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                            f'padding:13px;font-size:12px;color:#8b949e;">'
                            f'{analysis_date} AI 리포트 없음</div>',
                            unsafe_allow_html=True,
                        )
                    if st.button("🔄 AI 리포트", key="home_mr_btn", use_container_width=True,
                                 help="AI 시장 리포트 생성/재생성 (GPT-4o-mini)"):
                        from app.services.market_report_ai_service import generate_market_report as _gen_mr
                        with st.spinner("AI 리포트 생성 중..."):
                            res = _gen_mr(analysis_date)
                        if res.get("status") == "success":
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            err = res.get("message", "-")
                            if "크레딧" in err:
                                st.error(f"❌ 크레딧 부족: {err}")
                            else:
                                st.error(f"❌ {err}")

            with sec_col:
                st.markdown('<p class="sec-hd">업종별 등락률</p>', unsafe_allow_html=True)
                sectors = cached_sector_analysis(analysis_date, market)
                if sectors:
                    srt  = sorted(sectors, key=lambda x: x["avg_return"], reverse=True)
                    top  = srt[:5]
                    bot  = srt[-5:] if len(srt) >= 10 else srt[5:]
                    disp = sorted(top + [s for s in bot if s not in top],
                                  key=lambda x: x["avg_return"], reverse=True)
                    fig_bar = go.Figure(go.Bar(
                        y=[s["sector"][:12] for s in disp],
                        x=[s["avg_return"] for s in disp],
                        orientation="h",
                        marker_color=["#3fb950" if s["avg_return"] >= 0 else "#f85149" for s in disp],
                        text=[f"{s['avg_return']:+.2f}%" for s in disp],
                        textposition="outside",
                        textfont=dict(size=9, color="#e6edf3"),
                    ))
                    fig_bar.update_layout(
                        height=220, margin=dict(l=0, r=50, t=0, b=0),
                        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                        font=dict(color="#e6edf3", size=10),
                        xaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d", tickfont=dict(size=9)),
                        yaxis=dict(gridcolor="#21262d", tickfont=dict(size=10)),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, key="home_sector")
                else:
                    st.caption("업종 분석 데이터 없음 (분석 실행 후 확인)")

    # ── 종목 테이블 3열 (전체 너비) ──────────────────────────────
    if total > 0:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        t1, t2, t3 = st.columns(3)

        with t1:
            st.markdown('<p class="sec-hd">🔥 강세 TOP 20</p>', unsafe_allow_html=True)
            bullish = cached_bullish(analysis_date, market, limit=20)
            if bullish:
                df_b = pd.DataFrame(bullish)[
                    ["stock_code", "stock_name", "market", "daily_return", "return_5d", "bullish_score", "final_signal"]
                ]
                df_b.columns = ["코드", "종목명", "시장", "당일(%)", "5일(%)", "강세점수", "시그널"]
                df_b["당일(%)"]  = df_b["당일(%)"].apply(_fmt_return)
                df_b["5일(%)"]   = df_b["5일(%)"].apply(_fmt_return)
                df_b["강세점수"] = df_b["강세점수"].apply(_fmt_score)
                st.dataframe(df_b, use_container_width=True, hide_index=True, height=420)
            else:
                st.caption("데이터 없음")

        with t2:
            st.markdown('<p class="sec-hd">📉 약세 TOP 20</p>', unsafe_allow_html=True)
            bearish = cached_bearish(analysis_date, market, limit=20)
            if bearish:
                df_br = pd.DataFrame(bearish)[
                    ["stock_code", "stock_name", "market", "daily_return", "return_5d", "bearish_score", "final_signal"]
                ]
                df_br.columns = ["코드", "종목명", "시장", "당일(%)", "5일(%)", "약세점수", "시그널"]
                df_br["당일(%)"]  = df_br["당일(%)"].apply(_fmt_return)
                df_br["5일(%)"]   = df_br["5일(%)"].apply(_fmt_return)
                df_br["약세점수"] = df_br["약세점수"].apply(_fmt_score)
                st.dataframe(df_br, use_container_width=True, hide_index=True, height=420)
            else:
                st.caption("데이터 없음")

        with t3:
            st.markdown('<p class="sec-hd">📊 거래량 급증</p>', unsafe_allow_html=True)
            if high_vol:
                df_vol = pd.DataFrame(high_vol)[
                    ["stock_code", "stock_name", "market", "volume_ratio_5d", "volume_ratio_20d", "daily_return", "final_signal"]
                ]
                df_vol.columns = ["코드", "종목명", "시장", "거래량비(5일)", "거래량비(20일)", "당일(%)", "시그널"]
                df_vol["거래량비(5일)"]  = df_vol["거래량비(5일)"].apply(_fmt_ratio)
                df_vol["거래량비(20일)"] = df_vol["거래량비(20일)"].apply(_fmt_ratio)
                df_vol["당일(%)"]        = df_vol["당일(%)"].apply(_fmt_return)
                st.dataframe(df_vol, use_container_width=True, hide_index=True, height=420)
            else:
                st.caption("거래량 급증 종목 없음")


# ── 관심 종목 ─────────────────────────────────────────────────

def render_watchlist(analysis_date: date):
    st.title("⭐ 관심 종목 요약")

    # ── 자동 선정 버튼 ────────────────────────────────────────
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        if st.button("🤖 오늘 자동 선정", use_container_width=True,
                     help="오늘 분석 결과 기준으로 단기/장기 관심종목을 자동 선정합니다."):
            from app.services.watchlist_service import auto_select_watchlist
            with st.spinner("자동 선정 중..."):
                result = auto_select_watchlist(analysis_date)
            if result.get("status") == "success":
                s = result["short_term"]
                l = result["long_term"]
                st.success(
                    f"자동 선정 완료 — "
                    f"단기 {s['selected']}개(신규 {s['inserted']}/업데이트 {s['updated']}), "
                    f"장기 {l['selected']}개(신규 {l['inserted']}/업데이트 {l['updated']})"
                )
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"자동 선정 실패: {result.get('message', '-')}")
    with col_info:
        st.caption(
            "**자동 선정 기준** — "
            "단기: 강세 관심 시그널 + 모멘텀/거래량 점수 양호 + 위험 점수 과도 아님 | "
            "장기: 강세 관심·추세 유지 + MA 정배열 + 추세/상대강도 양호 *(참고용)*"
        )

    st.markdown("---")

    groups = cached_watchlist(analysis_date)

    if not groups:
        st.info("등록된 관심 종목 그룹이 없습니다.\n위 버튼으로 자동 선정하거나 API로 직접 등록하세요.")
        return

    for g in groups:
        label = f"📁 {g['group_name']}"
        if g["description"]:
            label += f"  —  {g['description']}"
        with st.expander(label, expanded=True):
            items = g["items"]
            if not items:
                st.caption("종목 없음")
                continue

            df_w = pd.DataFrame(items)[[
                "stock_code", "stock_name", "market",
                "daily_return", "return_5d", "return_20d",
                "bullish_score", "rsi14", "final_signal", "memo",
            ]]
            df_w.columns = ["코드", "종목명", "시장", "당일(%)", "5일(%)", "20일(%)", "강세점수", "RSI14", "시그널", "메모"]
            df_w["당일(%)"]  = df_w["당일(%)"].apply(_fmt_return)
            df_w["5일(%)"]   = df_w["5일(%)"].apply(_fmt_return)
            df_w["20일(%)"]  = df_w["20일(%)"].apply(_fmt_return)
            df_w["강세점수"] = df_w["강세점수"].apply(_fmt_score)
            df_w["RSI14"]    = df_w["RSI14"].apply(_fmt_score)
            df_w["시그널"]   = df_w["시그널"].apply(
                lambda s: f"{SIGNAL_ICON.get(s, '')} {s}" if s else "-"
            )
            st.dataframe(df_w, use_container_width=True, hide_index=True)

            # ── 종목별 선정 사유 ────────────────────────────
            is_auto = "(자동)" in g["group_name"]
            st.markdown("**📝 종목별 선정 사유** *(참고용)*")

            for item in items:
                signal = item.get("final_signal") or "-"
                icon   = SIGNAL_ICON.get(signal, "")
                memo   = item.get("memo") or ""
                signal_reason = item.get("signal_reason") or ""
                code  = item["stock_code"]
                name  = item["stock_name"]

                if is_auto and memo:
                    # 자동선정 그룹: memo에 단기/장기 선정 기준이 구조화돼 있음
                    # "|| 분석사유:" 구분자로 선정 이유와 분석 사유를 분리하여 표시
                    if "|| 분석사유:" in memo:
                        selection_part, analysis_part = memo.split("|| 분석사유:", 1)
                    else:
                        selection_part = memo
                        analysis_part  = signal_reason

                    st.markdown(
                        f"**{code} {name}** &nbsp; {icon} `{signal}`"
                    )
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;└ 📌 **선정 기준:** {selection_part.strip()}"
                    )
                    if analysis_part.strip():
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;└ 📊 **분석 사유:** {analysis_part.strip()}"
                        )
                else:
                    # 수동 등록 그룹: 기존 방식대로 _build_selection_reason 사용
                    reason = _build_selection_reason(item, g["group_name"])
                    st.markdown(
                        f"**{code} {name}** &nbsp; {icon} `{signal}` &nbsp;—&nbsp; {reason}"
                    )
                    if memo and memo != reason:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;└ 📝 메모: {memo}")

            st.caption("⚠️ 위 내용은 참고용 분석이며, 투자 권유가 아닙니다.")


# ── 종목 검색 ─────────────────────────────────────────────────

def _fetch_naver_board(stock_code: str, limit: int = 15) -> list[dict]:
    """네이버 파이낸스 종목토론 게시글 목록 스크래핑."""
    import re
    import urllib.request

    posts: list[dict] = []
    try:
        url = f"https://finance.naver.com/item/board.naver?code={stock_code}&page=1"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://finance.naver.com",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        html = raw.decode("utf-8", errors="replace")

        # 실제 HTML 구조 기반 패턴
        # <tr onMouseOver="mouseOver(this)" ...> 로 게시글 행 식별
        row_pat    = re.compile(r'<tr[^>]*onMouseOver="mouseOver[^>]*>(.*?)</tr>', re.DOTALL)
        # <a ... title="제목"> 속성에 제목 텍스트가 들어 있음
        title_pat  = re.compile(r'<td[^>]*class="title"[^>]*>.*?<a[^>]+title="([^"]+)"', re.DOTALL)
        # 날짜: <span class="tah p10 gray03">2026.05.20 23:13</span>
        date_pat   = re.compile(r'<span class="tah p10 gray03">(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})</span>')
        # 작성자: class="p11 align_right" td 안쪽 </span> 이후 텍스트
        writer_pat = re.compile(r'<td[^>]*class="p11 align_right"[^>]*>.*?</span>(.*?)</td>', re.DOTALL)
        # 조회수: <td><span class="tah p10 gray03">숫자</span></td>
        view_pat   = re.compile(r'<td><span class="tah p10 gray03">(\d+)</span></td>')
        # 공감: <strong class="tah p10 gray03 ">숫자</strong>
        agree_pat  = re.compile(r'<strong class="tah p10 gray03 ">(\d+)</strong>')

        for m in row_pat.finditer(html):
            row = m.group(1)
            t = title_pat.search(row)
            if not t:
                continue
            title = re.sub(r'\s+', ' ', t.group(1)).strip()
            if len(title) < 2:
                continue
            d = date_pat.search(row)
            w = writer_pat.search(row)
            v = view_pat.search(row)
            a = agree_pat.search(row)
            writer = re.sub(r'\s+', ' ', w.group(1)).strip() if w else "-"
            posts.append({
                "title":  title,
                "writer": writer if writer else "익명",
                "date":   d.group(1) if d else "-",
                "views":  v.group(1) if v else "-",
                "agrees": a.group(1) if a else "0",
            })
            if len(posts) >= limit:
                break
    except Exception as e:
        logger.debug(f"[토론] {stock_code} 스크래핑 실패: {e}")
    return posts


def render_stock_search(analysis_date: date):
    st.title("🔍 종목 검색")

    keyword = st.text_input("종목명 또는 코드 입력", placeholder="예: 삼성전자 또는 005930")
    if not keyword:
        return

    results = cached_stock_search(keyword)
    if not results:
        st.warning("검색 결과가 없습니다.")
        return

    options = {
        f"{r['stock_code']} - {r['stock_name']} ({r['market']})": r["stock_code"]
        for r in results
    }
    selected_label = st.selectbox("종목 선택", list(options.keys()))
    selected_code  = options[selected_label]

    st.markdown("---")
    _render_stock_detail(selected_code, analysis_date)


def _render_stock_detail(stock_code: str, analysis_date: date):
    df      = cached_price_history(stock_code, days=130)
    analysis = cached_stock_analysis(stock_code, analysis_date)

    # ── 종목 기본 정보 ────────────────────────────────────────
    latest = df.iloc[-1] if not df.empty else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("최근 거래일",  str(latest["trade_date"])          if latest is not None else "-")
    c2.metric("종가 (원)",    f"{int(latest['close_price']):,}"  if latest is not None else "-")
    c3.metric("거래량",       f"{int(latest['volume']):,}"       if latest is not None else "-")
    c4.metric("등락률",       f"{float(latest['change_rate']):+.2f}%" if (latest is not None and latest["change_rate"] is not None) else "-")

    st.markdown("---")

    # ── 시그널 + 분석 사유 ────────────────────────────────────
    if not analysis:
        st.warning(f"**{analysis_date}** 기준 분석 데이터가 없습니다.")
    else:
        signal = analysis.get("final_signal") or "-"
        icon   = SIGNAL_ICON.get(signal, "")
        reason = analysis.get("signal_reason") or ""

        col_sig, col_reason = st.columns([1, 3])
        with col_sig:
            st.markdown(f"## {icon} {signal}")
        with col_reason:
            if reason:
                st.info(reason)
            else:
                st.caption("분석 사유 정보 없음")

        st.markdown("---")

        # ── 수익률 / 이동평균 / 기술지표 / 점수 ─────────────────
        st.subheader("📊 분석 지표")
        col_ret, col_ma, col_tech, col_score = st.columns(4)

        with col_ret:
            st.markdown("**수익률**")
            st.metric(
                "당일",  _fmt_return(analysis.get("daily_return")),
                help="오늘 종가 기준 전일 대비 등락률입니다.",
            )
            st.metric(
                "5일",   _fmt_return(analysis.get("return_5d")),
                help="최근 5거래일(약 1주) 누적 수익률입니다.",
            )
            st.metric(
                "20일",  _fmt_return(analysis.get("return_20d")),
                help="최근 20거래일(약 1개월) 누적 수익률입니다.",
            )
            st.metric(
                "60일",  _fmt_return(analysis.get("return_60d")),
                help="최근 60거래일(약 3개월) 누적 수익률입니다.",
            )

        with col_ma:
            st.markdown("**이동평균 (원)**")
            ma_help = {
                "MA5":  "최근 5거래일 종가의 단순 이동평균. 단기 추세를 반영합니다.",
                "MA20": "최근 20거래일 종가의 단순 이동평균. 단기~중기 추세 기준선입니다.",
                "MA60": "최근 60거래일 종가의 단순 이동평균. 중기 추세를 나타냅니다.",
                "MA120":"최근 120거래일 종가의 단순 이동평균. 중장기 추세 기준선입니다.",
            }
            for lbl, key in [("MA5", "ma5"), ("MA20", "ma20"), ("MA60", "ma60"), ("MA120", "ma120")]:
                v = analysis.get(key)
                st.metric(lbl, f"{v:,.0f}" if v else "-", help=ma_help[lbl])

        with col_tech:
            st.markdown("**기술 지표**")
            st.metric(
                "RSI14", _fmt_score(analysis.get("rsi14")),
                help=(
                    "상대강도지수(RSI). 14일 기준 과매수/과매도 측정.\n"
                    "70 이상: 과매수 구간 / 30 이하: 과매도 구간 (참고용)"
                ),
            )
            v_vol = analysis.get("volatility_20d")
            st.metric(
                "변동성(20일)", f"{v_vol:.2f}%" if v_vol else "-",
                help="최근 20거래일 일별 수익률의 표준편차(연율화). 값이 클수록 가격 변동이 큽니다.",
            )
            st.metric(
                "상대강도", _fmt_return(analysis.get("relative_strength")),
                help="KOSPI 지수 대비 해당 종목의 20일 수익률 차이(%p). 양수면 시장 대비 강세입니다.",
            )
            st.metric(
                "거래량비(5일)", _fmt_ratio(analysis.get("volume_ratio_5d")),
                help="오늘 거래량 ÷ 최근 5일 평균 거래량. 1 이상이면 평소 대비 거래량 증가입니다.",
            )

        with col_score:
            st.markdown("**분석 점수**")
            st.metric(
                "강세점수", _fmt_score(analysis.get("bullish_score")),
                help="모멘텀·거래량·추세 점수를 종합한 강세 가능성 점수. 높을수록 상승 모멘텀이 강합니다. (참고용)",
            )
            st.metric(
                "약세점수", _fmt_score(analysis.get("bearish_score")),
                help="하락 위험 요인들을 종합한 약세 가능성 점수. 높을수록 하락 압력이 강합니다. (참고용)",
            )
            st.metric(
                "모멘텀", _fmt_score(analysis.get("momentum_score")),
                help="단기·중기 수익률과 이동평균 위치를 기반으로 산출한 가격 모멘텀 점수입니다.",
            )
            st.metric(
                "거래량", _fmt_score(analysis.get("volume_score")),
                help="최근 거래량 증가 정도를 점수화. 평균 대비 거래량이 많을수록 높습니다.",
            )
            st.metric(
                "추세", _fmt_score(analysis.get("trend_score")),
                help="MA5·MA20·MA60의 배열과 기울기를 종합해 산출한 추세 강도 점수입니다.",
            )
            st.metric(
                "위험", _fmt_score(analysis.get("risk_score")),
                help="변동성·하락폭·공시 위험 등을 종합한 위험 점수. 높을수록 단기 변동성이 크거나 위험 신호가 있습니다.",
            )

        st.markdown("---")

    # ── 차트 ──────────────────────────────────────────────────
    st.subheader("📈 가격 차트 (최근 60일)")
    if df.empty:
        st.info("시세 데이터 없음 — 데이터 수집 후 다시 시도하세요.")
    else:
        df60 = df.tail(60).copy()
        st.plotly_chart(_make_price_chart(df60, stock_code), use_container_width=True)
        st.plotly_chart(_make_volume_chart(df60, stock_code), use_container_width=True)

    if not analysis:
        return

    # ── 카드 3종 ──────────────────────────────────────────────
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.subheader("📝 분석 사유")
        txt = analysis.get("signal_reason") or "분석 사유 정보가 없습니다."
        st.markdown(txt)

    with col_b:
        st.subheader("⚠️ 위험 요인")
        risk = analysis.get("risk_score") or 0
        vol  = analysis.get("volatility_20d")
        if risk >= 20:
            st.error(f"위험 점수 **{risk:.1f}점** — 고위험 구간, 분산 투자 고려 필요")
        elif risk >= 10:
            st.warning(f"위험 점수 **{risk:.1f}점** — 변동성 점검이 필요합니다")
        else:
            st.success(f"위험 점수 **{risk:.1f}점** — 상대적으로 안정적인 구간")
        if vol:
            st.caption(f"20일 변동성: {vol:.2f}%")

    with col_c:
        st.subheader("📌 참고 안내")
        st.info(
            "본 분석은 가격, 거래량, 추세, 변동성 데이터를 기준으로 한 **참고용** 분석입니다. "
            "투자 판단은 사용자 본인 책임입니다."
        )

    # ── 향후 전망 분석 ────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔮 향후 전망 분석")
    st.caption(
        "가격·거래량·이동평균·기술 지표를 기반으로 한 **참고용** 분석입니다. "
        "미래 가격을 예측하는 것이 아니며, 투자 권유가 아닙니다."
    )

    latest_close = float(latest["close_price"]) if latest is not None else None
    outlook = _build_outlook_analysis(analysis, latest_close)

    col_sh, col_mid = st.columns(2)

    with col_sh:
        st.markdown("#### 📅 단기 전망 (1~2주)")
        for pt in outlook["short_pts"]:
            st.markdown(f"- {pt}")

    with col_mid:
        st.markdown("#### 📆 중기 전망 (1~3개월)")
        for pt in outlook["mid_pts"]:
            st.markdown(f"- {pt}")

    # 지지/저항
    support    = outlook["support"]
    resistance = outlook["resistance"]
    if support or resistance:
        st.markdown("#### 📏 주요 가격 레벨")
        lc1, lc2 = st.columns(2)
        with lc1:
            st.markdown("**🟢 지지 레벨** *(현재가 위에서 하방 지지 가능)*")
            if support:
                for item in support:
                    st.markdown(f"- {item}")
            else:
                st.caption("현재가가 주요 이동평균 아래에 위치")
        with lc2:
            st.markdown("**🔴 저항 레벨** *(현재가 위에 위치한 돌파 대상)*")
            if resistance:
                for item in resistance:
                    st.markdown(f"- {item}")
            else:
                st.caption("현재가가 주요 이동평균 위에 위치")

    # 시나리오 3종
    st.markdown("#### 📊 시나리오별 분석")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.success(f"**🟢 강세 시나리오**\n\n{outlook['bull_outlook']}")
    with sc2:
        st.error(f"**🔴 약세 시나리오**\n\n{outlook['bear_outlook']}")
    with sc3:
        st.info(f"**🟡 중립 / 관망**\n\n{outlook['neutral_outlook']}")

    st.caption(
        "⚠️ 위 전망은 기술적 지표 기반 참고용 분석이며, "
        "실제 수익·손실을 보장하지 않습니다. 투자 판단은 사용자 본인 책임입니다."
    )

    # ── AI 분석 해설 ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("🤖 AI 분석 해설")
    st.caption("GPT-4o-mini 기반 자연어 해설입니다. 참고용이며 투자 권유가 아닙니다.")

    from app.config import settings as _cfg
    ai_configured = bool(getattr(_cfg, "OPENAI_API_KEY", ""))

    if not ai_configured:
        st.warning(
            "AI 분석을 사용하려면 `.env` 파일에 `OPENAI_API_KEY`를 설정하세요.\n\n"
            "```\nOPENAI_API_KEY=sk-...\n```"
        )
    else:
        ai = cached_ai_analysis(stock_code, analysis_date)

        col_ai_btn, col_ai_info = st.columns([1, 4])
        with col_ai_btn:
            if st.button("🔄 AI 분석 요청", use_container_width=True,
                         help="OpenAI GPT-4o-mini로 이 종목의 AI 해설을 새로 생성합니다."):
                from app.services.ai_analysis_service import analyze_stock as _ai_analyze
                with st.spinner("AI 분석 중 (GPT-4o-mini 호출)..."):
                    result = _ai_analyze(stock_code, analysis_date)
                if result.get("status") == "success":
                    st.success("AI 분석 완료")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    err_msg = result.get("message", "알 수 없는 오류")
                    if "크레딧" in err_msg or "insufficient_quota" in err_msg:
                        st.error(
                            "❌ **OpenAI 크레딧 부족**\n\n"
                            "https://platform.openai.com/account/billing 에서 "
                            "결제 정보를 등록하거나 크레딧을 충전하세요.\n\n"
                            f"상세: {err_msg}"
                        )
                    elif "유효하지 않" in err_msg or "Authentication" in err_msg:
                        st.error(
                            "❌ **API 키 오류**\n\n"
                            "`.env`의 `OPENAI_API_KEY` 값을 확인하세요.\n\n"
                            f"상세: {err_msg}"
                        )
                    else:
                        st.error(f"❌ AI 분석 실패: {err_msg}")
        with col_ai_info:
            if ai:
                st.caption(f"마지막 생성: {ai.get('updated_at', '-')}")
            else:
                st.caption("아직 AI 분석 결과가 없습니다. 위 버튼으로 생성하세요.")

        if ai:
            ai_cols = st.columns(2)

            with ai_cols[0]:
                if ai.get("ai_summary"):
                    st.markdown("**📋 종합 요약**")
                    st.info(ai["ai_summary"])
                if ai.get("ai_signal_comment"):
                    st.markdown("**📊 시그널 해석**")
                    st.info(ai["ai_signal_comment"])

            with ai_cols[1]:
                if ai.get("ai_trend_comment"):
                    st.markdown("**📈 추세 해설**")
                    st.info(ai["ai_trend_comment"])
                if ai.get("ai_volume_comment"):
                    st.markdown("**📊 거래량 해설**")
                    st.info(ai["ai_volume_comment"])

            if ai.get("ai_risk_comment"):
                st.markdown("**⚠️ 위험 요인 해설**")
                st.warning(ai["ai_risk_comment"])

            st.caption(
                "⚠️ 위 AI 해설은 기술적 지표 기반 참고용 자연어 분석입니다. "
                "실제 투자 결과와 다를 수 있으며, 투자 판단은 사용자 본인 책임입니다."
            )

    # ── AI 공시 분석 ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("📢 AI 공시 분석")
    st.caption("공시 제목·유형·요약을 GPT-4o-mini로 해설합니다. 참고용이며 투자 권유가 아닙니다.")

    from app.config import settings as _cfg2
    if not bool(getattr(_cfg2, "OPENAI_API_KEY", "")):
        st.warning("AI 공시 분석을 사용하려면 `.env` 파일에 `OPENAI_API_KEY`를 설정하세요.")
    else:
        disc_ai_list = cached_disclosure_ai(stock_code)
        raw_discs    = cached_stock_disclosures(stock_code)

        col_dbtn, col_dinfo = st.columns([1, 4])
        with col_dbtn:
            if st.button("🔄 공시 AI 분석", use_container_width=True,
                         help="최근 공시 5건에 대해 AI 해설을 생성합니다."):
                from app.services.disclosure_ai_service import analyze_stock_disclosures as _disc_ai
                with st.spinner("공시 AI 분석 중..."):
                    dresult = _disc_ai(stock_code, limit=5, skip_existing=False)
                if dresult.get("status") in ("success", "partial"):
                    st.success(
                        f"완료 — 처리 {dresult['processed']}건, "
                        f"스킵 {dresult['skipped']}건"
                    )
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"❌ 공시 AI 분석 실패: {dresult.get('message', '-')}")
        with col_dinfo:
            if disc_ai_list:
                st.caption(f"분석된 공시 {len(disc_ai_list)}건 (최근 10건 기준)")
            elif raw_discs:
                st.caption(f"공시 {len(raw_discs)}건 있음 — 위 버튼으로 AI 분석을 실행하세요.")
            else:
                st.caption("이 종목의 공시 데이터가 없습니다.")

        # ── 분석 결과 표시 ────────────────────────────────────
        RISK_COLOR = {"낮음": "🟢", "보통": "🟡", "높음": "🔴", "주의": "⚠️"}

        if disc_ai_list:
            for item in disc_ai_list:
                risk     = item.get("ai_disclosure_risk") or "보통"
                risk_icon = RISK_COLOR.get(risk, "⬜")
                with st.expander(
                    f"{risk_icon} [{item['report_date']}] {item['title']}  |  유형: {item['disclosure_type']}",
                    expanded=False,
                ):
                    r1, r2 = st.columns([3, 1])
                    with r1:
                        st.markdown("**📋 공시 요약 (AI)**")
                        st.info(item.get("ai_disclosure_summary") or "-")
                        st.markdown("**📈 시장 영향 참고**")
                        st.info(item.get("ai_market_impact") or "-")
                    with r2:
                        st.markdown("**위험도**")
                        if risk == "낮음":
                            st.success(f"{risk_icon} {risk}")
                        elif risk in ("높음", "주의"):
                            st.error(f"{risk_icon} {risk}")
                        else:
                            st.warning(f"{risk_icon} {risk}")
                        st.caption(f"분석일: {item.get('updated_at', '-')}")
                    st.caption("⚠️ 본 공시 분석은 참고용이며 투자 권유가 아닙니다.")

        elif raw_discs:
            # AI 분석 미실행 시 원본 공시 목록만 표시
            st.markdown("**최근 공시 목록** *(AI 분석 미실행)*")
            for d in raw_discs[:5]:
                st.markdown(f"- **{d['report_date']}** | {d['title']} | 유형: {d['disclosure_type']}")

    # ── 종목토론 ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💬 종목토론")
    st.caption("네이버 파이낸스 종목토론 최근 게시글입니다. 참고용이며 투자 권유가 아닙니다.")
    with st.spinner("토론 목록 불러오는 중..."):
        board_posts = _fetch_naver_board(stock_code, limit=15)
    if board_posts:
        for p in board_posts:
            st.markdown(
                f"**{p['title']}**  \n"
                f"<span style='font-size:0.8em;color:gray;'>"
                f"👤 {p['writer']} &nbsp;·&nbsp; 🕐 {p['date']} &nbsp;·&nbsp; 👁 {p['views']} &nbsp;·&nbsp; 👍 {p['agrees']}"
                f"</span>",
                unsafe_allow_html=True,
            )
            st.divider()
    else:
        st.caption("종목토론 게시글을 불러오지 못했습니다.")


def _make_price_chart(df: pd.DataFrame, stock_code: str) -> go.Figure:
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df["close_price"].astype(float)

    fig = go.Figure()
    if all(c in df.columns for c in ["open_price", "high_price", "low_price"]):
        fig.add_trace(go.Candlestick(
            x=df["trade_date"],
            open=df["open_price"].astype(float),
            high=df["high_price"].astype(float),
            low=df["low_price"].astype(float),
            close=close,
            name="가격",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=df["trade_date"], y=close, name="종가", line=dict(color="#26a69a")
        ))

    for period, color in [(5, "#ffd600"), (20, "#42a5f5"), (60, "#ef9a9a"), (120, "#ce93d8")]:
        if len(close) >= period:
            fig.add_trace(go.Scatter(
                x=df["trade_date"],
                y=close.rolling(period).mean(),
                name=f"MA{period}",
                line=dict(color=color, width=1),
            ))

    fig.update_layout(
        title=f"{stock_code} 주가 차트",
        xaxis_title="날짜",
        yaxis_title="가격 (원)",
        height=420,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def _make_volume_chart(df: pd.DataFrame, stock_code: str) -> go.Figure:
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    colors = [
        "#ef5350" if (r is not None and float(r) >= 0) else "#26a69a"
        for r in df["change_rate"]
    ]
    fig = go.Figure(go.Bar(
        x=df["trade_date"],
        y=df["volume"].astype(float),
        name="거래량",
        marker_color=colors,
    ))
    fig.update_layout(
        title=f"{stock_code} 거래량",
        xaxis_title="날짜",
        yaxis_title="거래량",
        height=200,
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=40, r=20, t=40, b=30),
    )
    return fig


# ── AI 분석 페이지 ────────────────────────────────────────────

_RISK_ICONS = {"낮음": "🟢", "보통": "🟡", "높음": "🔴", "주의": "⚠️"}


def _render_ai_tab_market(analysis_date: date):
    market_report = cached_market_report_ai(analysis_date)

    btn_c, info_c = st.columns([1, 4])
    with btn_c:
        if st.button("🔄 AI 리포트 생성", key="ai_tab_mkt_gen", use_container_width=True):
            from app.services.market_report_ai_service import generate_market_report as _gen
            with st.spinner("AI 시장 리포트 생성 중..."):
                r = _gen(analysis_date)
            if r.get("status") == "success":
                st.success("생성 완료")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"실패: {r.get('message', '-')}")
    with info_c:
        if market_report:
            st.caption(f"마지막 생성: {market_report.get('updated_at', '-')}")
        else:
            st.caption(f"{analysis_date} AI 시장 리포트가 없습니다. 위 버튼으로 생성하세요.")

    if not market_report:
        st.info("위 버튼으로 AI 시장 리포트를 생성하세요.")
        return

    if market_report.get("market_ai_summary"):
        st.info(f"**📋 시장 종합 요약**\n\n{market_report['market_ai_summary']}")

    col1, col2 = st.columns(2)
    with col1:
        if market_report.get("bullish_market_comment"):
            st.success(f"**🔥 강세 흐름**\n\n{market_report['bullish_market_comment']}")
        if market_report.get("volume_market_comment"):
            st.info(f"**📊 거래량 특징**\n\n{market_report['volume_market_comment']}")
    with col2:
        if market_report.get("bearish_market_comment"):
            st.error(f"**📉 약세 흐름**\n\n{market_report['bearish_market_comment']}")
        if market_report.get("risk_market_comment"):
            st.warning(f"**⚠️ 위험 요소**\n\n{market_report['risk_market_comment']}")

    st.caption("⚠️ 본 리포트는 참고용이며 투자 권유가 아닙니다.")


def _render_ai_tab_watchlist(analysis_date: date):
    items = cached_watchlist_ai(analysis_date)

    if not items:
        st.info("등록된 관심 종목이 없습니다.")
        return

    has_ai = [i for i in items if i["has_ai"]]
    no_ai  = [i for i in items if not i["has_ai"]]
    st.caption(f"관심 종목 {len(items)}개  |  AI 분석 완료 {len(has_ai)}개  |  미완료 {len(no_ai)}개")

    if no_ai:
        with st.expander(f"⚠️ AI 분석 미완료 {len(no_ai)}개", expanded=False):
            st.caption(", ".join(f"`{i['stock_code']}`" for i in no_ai[:15]))
            if st.button("🔄 미완료 일괄 AI 분석", key="ai_wl_batch"):
                from app.services.ai_analysis_service import analyze_stock as _ai_s
                prog = st.progress(0)
                for idx, item in enumerate(no_ai):
                    _ai_s(item["stock_code"], analysis_date)
                    prog.progress((idx + 1) / len(no_ai))
                st.cache_data.clear()
                st.rerun()

    if not has_ai:
        st.info("AI 분석이 완료된 관심 종목이 없습니다.")
        return

    for item in has_ai:
        signal = item.get("final_signal") or "-"
        icon   = SIGNAL_ICON.get(signal, "")
        with st.expander(
            f"{icon} **{item['stock_code']} {item['stock_name']}**  "
            f"| {item['group_name']}  | 시그널: {signal}",
            expanded=False,
        ):
            c1, c2 = st.columns([3, 1])
            with c1:
                if item.get("ai_summary"):
                    st.markdown("**📋 AI 종합 요약**")
                    st.info(item["ai_summary"])
                if item.get("ai_signal_comment"):
                    st.markdown("**📊 AI 시그널 해석**")
                    st.info(item["ai_signal_comment"])
                if item.get("ai_trend_comment"):
                    st.markdown("**📈 AI 추세 설명**")
                    st.info(item["ai_trend_comment"])
            with c2:
                st.metric("당일", _fmt_return(item.get("daily_return")))
                st.metric("위험점수", _fmt_score(item.get("risk_score")))
                st.metric("강세점수", _fmt_score(item.get("bullish_score")))
                st.caption(f"갱신: {item.get('ai_updated_at', '-')}")


def _render_ai_tab_risk(analysis_date: date):
    stocks = cached_risk_stocks_ai(analysis_date)

    if not stocks:
        st.info(f"{analysis_date} 기준 위험 점수 15점 이상 종목이 없습니다.")
        return

    has_ai = [s for s in stocks if s["has_ai"]]
    st.caption(f"위험 종목 {len(stocks)}개  |  AI 분석 {len(has_ai)}개 완료")

    for stock in stocks:
        risk   = stock["risk_score"]
        signal = stock.get("final_signal") or "-"
        icon   = SIGNAL_ICON.get(signal, "")
        vol    = stock.get("volatility_20d")

        with st.expander(
            f"{icon} **{stock['stock_code']} {stock['stock_name']}**  "
            f"| 위험점수: {risk:.1f}  | 변동성: {vol:.1f}%" if vol else
            f"{icon} **{stock['stock_code']} {stock['stock_name']}**  | 위험점수: {risk:.1f}",
            expanded=False,
        ):
            if stock.get("ai_risk_comment"):
                (st.error if risk >= 25 else st.warning if risk >= 20 else st.info)(
                    f"**⚠️ AI 위험 분석**\n\n{stock['ai_risk_comment']}"
                )
            if stock.get("ai_summary"):
                st.info(f"**📋 AI 종합 요약**\n\n{stock['ai_summary']}")
            if not stock["has_ai"]:
                st.caption("AI 분석 없음")
                if st.button("🔄 AI 분석 생성", key=f"risk_ai_{stock['stock_code']}"):
                    from app.services.ai_analysis_service import analyze_stock as _ai_s
                    with st.spinner("분석 중..."):
                        r = _ai_s(stock["stock_code"], analysis_date)
                    if r.get("status") == "success":
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(r.get("message", "-"))


def _render_ai_tab_disclosure(analysis_date: date):
    items = cached_all_disclosure_ai(limit=30)

    if not items:
        st.info("분석된 공시 데이터가 없습니다. 종목 검색 → AI 공시 분석 섹션에서 생성하세요.")
        return

    risk_filter = st.selectbox(
        "위험도 필터", ["전체", "주의", "높음", "보통", "낮음"], key="ai_disc_tab_filter"
    )
    filtered = items if risk_filter == "전체" else [
        i for i in items if i.get("ai_disclosure_risk") == risk_filter
    ]
    st.caption(f"AI 분석 공시 {len(items)}건  |  표시 {len(filtered)}건")

    for item in filtered:
        risk = item.get("ai_disclosure_risk") or "보통"
        icon = _RISK_ICONS.get(risk, "⬜")
        with st.expander(
            f"{icon} [{item['report_date']}] **{item['stock_code']}** — {item['title'][:55]}",
            expanded=False,
        ):
            rc1, rc2 = st.columns([3, 1])
            with rc1:
                if item.get("ai_disclosure_summary"):
                    st.markdown("**📋 공시 AI 요약**")
                    st.info(item["ai_disclosure_summary"])
                if item.get("ai_market_impact"):
                    st.markdown("**📈 시장 영향 참고**")
                    st.info(item["ai_market_impact"])
            with rc2:
                if risk in ("높음", "주의"):
                    st.error(f"{icon} {risk}")
                elif risk == "보통":
                    st.warning(f"{icon} {risk}")
                else:
                    st.success(f"{icon} {risk}")
                st.caption(f"유형: {item['disclosure_type']}")


def _render_ai_tab_volume(analysis_date: date):
    stocks = cached_volume_stocks_ai(analysis_date)

    if not stocks:
        st.info(f"{analysis_date} 기준 거래량 급증(5일 평균 2배 이상) 종목이 없습니다.")
        return

    has_ai = [s for s in stocks if s["has_ai"]]
    st.caption(f"거래량 급증 종목 {len(stocks)}개  |  AI 분석 {len(has_ai)}개 완료")

    for stock in stocks:
        signal = stock.get("final_signal") or "-"
        icon   = SIGNAL_ICON.get(signal, "")
        vr5    = stock.get("volume_ratio_5d") or 0

        with st.expander(
            f"{icon} **{stock['stock_code']} {stock['stock_name']}**  "
            f"| 거래량비(5일): {vr5:.1f}배  | 당일: {_fmt_return(stock.get('daily_return'))}",
            expanded=False,
        ):
            if stock.get("ai_volume_comment"):
                st.info(f"**📊 AI 거래량 해설**\n\n{stock['ai_volume_comment']}")
            if stock.get("ai_summary"):
                st.info(f"**📋 AI 종합 요약**\n\n{stock['ai_summary']}")
            if not stock["has_ai"]:
                st.caption("AI 분석 없음")
                if st.button("🔄 AI 분석 생성", key=f"vol_ai_{stock['stock_code']}"):
                    from app.services.ai_analysis_service import analyze_stock as _ai_s
                    with st.spinner("분석 중..."):
                        r = _ai_s(stock["stock_code"], analysis_date)
                    if r.get("status") == "success":
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(r.get("message", "-"))


def _render_ai_stock_detail_section(analysis_date: date):
    keyword = st.text_input(
        "종목명 또는 코드 입력",
        placeholder="예: 삼성전자 또는 005930",
        key="ai_detail_kw",
    )
    if not keyword:
        st.caption("종목을 입력하면 AI 분석 5개 카드를 표시합니다.")
        return

    results = cached_stock_search(keyword)
    if not results:
        st.warning("검색 결과가 없습니다.")
        return

    options = {
        f"{r['stock_code']} - {r['stock_name']} ({r['market']})": r["stock_code"]
        for r in results
    }
    selected_label = st.selectbox("종목 선택", list(options.keys()), key="ai_detail_sel")
    selected_code  = options[selected_label]

    st.markdown("---")

    ai           = cached_ai_analysis(selected_code, analysis_date)
    disc_ai_list = cached_disclosure_ai(selected_code, limit=3)

    btn_c, info_c = st.columns([1, 4])
    with btn_c:
        if st.button("🔄 AI 분석 생성/갱신", key="ai_detail_gen", use_container_width=True):
            from app.services.ai_analysis_service import analyze_stock as _ai_s
            with st.spinner("AI 분석 중..."):
                r = _ai_s(selected_code, analysis_date)
            if r.get("status") == "success":
                st.success("완료")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"실패: {r.get('message', '-')}")
    with info_c:
        if ai:
            st.caption(f"마지막 AI 분석: {ai.get('updated_at', '-')}")
        else:
            st.caption("AI 분석 데이터 없음 — 위 버튼으로 생성하세요.")

    if not ai:
        return

    st.markdown(f"#### {selected_code} AI 상세 분석")

    # 카드 1·2
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📋 AI 종목 요약**")
        st.info(ai.get("ai_summary") or "-")
    with col2:
        st.markdown("**📈 AI 추세 설명**")
        st.info(ai.get("ai_trend_comment") or "-")

    # 카드 3·4
    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**⚠️ AI 위험 설명**")
        st.warning(ai.get("ai_risk_comment") or "-")
    with col4:
        st.markdown("**📊 AI 거래량 설명**")
        st.info(ai.get("ai_volume_comment") or "-")

    # 카드 5 (공시 영향)
    st.markdown("**📢 AI 공시 영향 설명**")
    if disc_ai_list:
        for d in disc_ai_list:
            risk = d.get("ai_disclosure_risk") or "보통"
            icon = _RISK_ICONS.get(risk, "⬜")
            st.markdown(f"{icon} **{d['report_date']}** | {d['title'][:55]}")
            if d.get("ai_market_impact"):
                st.info(d["ai_market_impact"])
            if d.get("ai_disclosure_summary"):
                st.caption(d["ai_disclosure_summary"])
    else:
        st.caption("이 종목의 공시 AI 분석이 없습니다. 종목 검색 페이지에서 생성하세요.")

    # ── 종목토론 ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**💬 종목토론 (네이버 파이낸스)**")
    st.caption("최근 게시글입니다. 참고용이며 투자 권유가 아닙니다.")
    with st.spinner("토론 목록 불러오는 중..."):
        board_posts = _fetch_naver_board(selected_code, limit=15)
    if board_posts:
        for p in board_posts:
            st.markdown(
                f"**{p['title']}**  \n"
                f"<span style='font-size:0.8em;color:gray;'>"
                f"👤 {p['writer']} &nbsp;·&nbsp; 🕐 {p['date']} &nbsp;·&nbsp; 👁 {p['views']} &nbsp;·&nbsp; 👍 {p['agrees']}"
                f"</span>",
                unsafe_allow_html=True,
            )
            st.divider()
    else:
        st.caption("종목토론 게시글을 불러오지 못했습니다.")

    st.caption("⚠️ 본 AI 분석은 기술적 지표 기반 참고용이며 투자 권유가 아닙니다.")


def render_ai_analysis(analysis_date: date, market=None):
    market_label = market or "전체"
    st.title(f"🤖 AI 분석  |  {analysis_date}  |  {market_label}")
    st.caption("GPT-4o-mini 기반 AI 분석 종합 대시보드  ·  참고용  ·  투자 권유 아님")

    from app.config import settings as _ai_cfg
    if not bool(getattr(_ai_cfg, "OPENAI_API_KEY", "")):
        st.warning("AI 분석을 사용하려면 `.env`에 `OPENAI_API_KEY`를 설정하세요.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 시장 요약", "⭐ 관심 종목 AI", "⚠️ 위험 분석", "📢 공시 분석", "📊 거래량 분석",
    ])

    with tab1:
        _render_ai_tab_market(analysis_date)
    with tab2:
        _render_ai_tab_watchlist(analysis_date)
    with tab3:
        _render_ai_tab_risk(analysis_date)
    with tab4:
        _render_ai_tab_disclosure(analysis_date)
    with tab5:
        _render_ai_tab_volume(analysis_date)

    st.markdown("---")
    st.subheader("🔍 종목 AI 상세 분석")
    st.caption("종목을 검색하면 AI 종합 분석 5개 카드를 표시합니다.")
    _render_ai_stock_detail_section(analysis_date)


# ── 최신 리포트 ───────────────────────────────────────────────

def render_report():
    st.title("📋 최신 리포트")
    report = get_latest_report()
    if not report:
        st.info("리포트가 없습니다. `POST /api/reports/generate`를 실행하세요.")
        return

    st.caption(f"리포트 날짜: {report.get('report_date', '-')}")
    md = report.get("markdown_content", "")
    if md:
        st.markdown(md)
    else:
        st.json(report.get("json_content", {}))


# ── 스케줄러 ──────────────────────────────────────────────────

def _get_scheduler_logs(limit=20):
    session = get_db_session()
    try:
        q = (
            select(CollectorLog)
            .where(CollectorLog.collector_name.like("scheduler%"))
            .order_by(CollectorLog.id.desc())
            .limit(limit)
        )
        rows = session.execute(q).scalars().all()
        return [
            {
                "id":             r.id,
                "collector_name": r.collector_name,
                "target_date":    str(r.target_date) if r.target_date else "-",
                "status":         r.status,
                "message":        r.message or "-",
                "started_at":     str(r.started_at)[:19] if r.started_at else "-",
                "finished_at":    str(r.finished_at)[:19] if r.finished_at else "-",
            }
            for r in rows
        ]
    finally:
        session.close()


def render_scheduler():
    st.title("⚙️ 스케줄러")

    from app.services.scheduler_service import (
        get_scheduler_status,
        job_ai_disclosure_analysis,
        job_ai_market_report,
        job_ai_stock_analysis,
        job_auto_watchlist,
        job_collect_stocks,
        job_collect_prices,
        job_run_analysis,
        job_generate_report,
        run_ai_pipeline,
        run_daily_pipeline,
    )

    # ── 스케줄러 상태 ─────────────────────────────────────────
    st.subheader("스케줄러 상태")
    status = get_scheduler_status()
    running = status.get("running", False)

    col_status, col_next = st.columns(2)
    col_status.metric(
        "실행 상태",
        "🟢 실행 중" if running else "🔴 중지됨",
    )

    jobs = status.get("jobs", [])
    next_run = jobs[0]["next_run"] if jobs else None
    col_next.metric(
        "다음 실행 예정",
        next_run[:16] if next_run else "미등록",
    )

    if jobs:
        with st.expander("등록된 잡 목록", expanded=False):
            df_jobs = pd.DataFrame(jobs)[["id", "name", "next_run", "trigger"]]
            df_jobs.columns = ["ID", "이름", "다음 실행", "트리거"]
            st.dataframe(df_jobs, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── 수동 실행 버튼 ───────────────────────────────────────
    st.subheader("수동 실행")
    st.caption("각 단계를 개별 실행하거나 파이프라인을 한 번에 실행할 수 있습니다.")

    run_result = None

    # 행 1: 기본 파이프라인
    st.markdown("**기본 파이프라인**")
    b1 = st.columns(6)

    if b1[0].button("📋 종목 수집", use_container_width=True):
        with st.spinner("종목 수집 중..."):
            run_result = ("종목 수집", job_collect_stocks())

    if b1[1].button("💰 가격 수집(5일)", use_container_width=True):
        with st.spinner("가격 수집 중..."):
            run_result = ("가격 수집", job_collect_prices(days=5))

    if b1[2].button("📊 분석 실행", use_container_width=True):
        with st.spinner("분석 중..."):
            run_result = ("분석 실행", job_run_analysis())

    if b1[3].button("⭐ 관심종목 선정", use_container_width=True):
        with st.spinner("자동 선정 중..."):
            run_result = ("관심종목 자동 선정", job_auto_watchlist())

    if b1[4].button("📝 리포트 저장", use_container_width=True):
        with st.spinner("리포트 생성 중..."):
            run_result = ("리포트 저장", job_generate_report())

    if b1[5].button("🚀 전체 파이프라인", use_container_width=True):
        with st.spinner("전체 파이프라인 실행 중 (수분 소요)..."):
            run_result = ("전체 파이프라인", run_daily_pipeline())

    st.markdown("**AI 파이프라인**")
    b2 = st.columns(4)

    if b2[0].button("🤖 AI 종목 분석", use_container_width=True,
                    help="오늘 분석 상위 30종목에 GPT-4o-mini AI 해설 생성"):
        with st.spinner("AI 종목 분석 중 (수분 소요)..."):
            run_result = ("AI 종목 분석", job_ai_stock_analysis(limit=30))

    if b2[1].button("📢 AI 공시 분석", use_container_width=True,
                    help="오늘 공시 종목에 GPT-4o-mini AI 공시 해설 생성"):
        with st.spinner("AI 공시 분석 중..."):
            run_result = ("AI 공시 분석", job_ai_disclosure_analysis())

    if b2[2].button("📊 AI 시장 리포트", use_container_width=True,
                    help="시장 전체 데이터를 GPT-4o-mini로 종합 분석"):
        with st.spinner("AI 시장 리포트 생성 중..."):
            run_result = ("AI 시장 리포트", job_ai_market_report())

    if b2[3].button("⚡ AI 파이프라인", use_container_width=True,
                    help="AI 종목 분석 → AI 공시 분석 → AI 시장 리포트 순서 실행"):
        with st.spinner("AI 파이프라인 실행 중 (수분 소요)..."):
            run_result = ("AI 파이프라인", run_ai_pipeline())

    if run_result:
        label, result = run_result
        status_val = result.get("status", "unknown")
        if status_val in ("success", "ok", "partial"):
            st.success(f"**{label}** 완료 — status: `{status_val}`")
        else:
            st.error(f"**{label}** 실패 — {result.get('message', result)}")
        with st.expander("상세 결과", expanded=False):
            st.json(result)

    st.markdown("---")

    # ── 최근 실행 로그 ───────────────────────────────────────
    st.subheader("최근 스케줄러 실행 로그")
    if st.button("🔄 새로고침"):
        st.rerun()

    logs = _get_scheduler_logs(limit=30)
    if not logs:
        st.info("스케줄러 실행 이력이 없습니다.")
    else:
        df_logs = pd.DataFrame(logs)[
            ["collector_name", "target_date", "status", "message", "started_at", "finished_at"]
        ]
        df_logs.columns = ["작업 이름", "대상 날짜", "상태", "메시지", "시작 시각", "완료 시각"]

        def _status_icon(s):
            return {"success": "✅ success", "error": "❌ error", "partial": "⚠️ partial"}.get(s, s)

        df_logs["상태"] = df_logs["상태"].apply(_status_icon)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)


# ── 수급 분석 ─────────────────────────────────────────────────

_SUPPLY_SIGNAL_COLOR = {
    "쌍끌기 강매수":        "#1a7f37",
    "외국인+기관 동반매수": "#2ea043",
    "외국인 지속 매수":     "#2ea043",
    "기관 지속 매수":       "#388bfd",
    "외국인 매수 우위":     "#57ab5a",
    "기관 매수 우위":       "#6cb6ff",
    "혼조":                 "#8b949e",
    "외국인 지속 매도":     "#e5534b",
    "기관·외국인 매도 우위":"#e5534b",
    "외국인+기관 동반매도": "#b91c1c",
}

_SUPPLY_SIGNAL_ICON = {
    "쌍끌기 강매수":        "🔥",
    "외국인+기관 동반매수": "🟢",
    "외국인 지속 매수":     "🔺",
    "기관 지속 매수":       "🔵",
    "외국인 매수 우위":     "↑",
    "기관 매수 우위":       "↑",
    "혼조":                 "▪️",
    "외국인 지속 매도":     "🔻",
    "기관·외국인 매도 우위":"🔻",
    "외국인+기관 동반매도": "🚨",
}


def _supply_score_bar(score: float) -> str:
    """수급 점수 -100~+100 시각화 바."""
    pct = min(abs(score) / 100 * 50, 50)
    color = "#2ea043" if score >= 0 else "#e5534b"
    margin = "left:50%" if score >= 0 else f"left:calc(50% - {pct:.1f}%)"
    return (
        f'<div style="position:relative;height:8px;background:rgba(128,128,128,0.15);'
        f'border-radius:4px;margin:6px 0;">'
        f'<div style="position:absolute;top:0;{margin};width:{pct:.1f}%;height:100%;'
        f'background:{color};border-radius:4px;"></div>'
        f'<div style="position:absolute;left:50%;top:-2px;width:2px;height:12px;'
        f'background:rgba(128,128,128,0.4);"></div></div>'
    )


def _net_buy_fmt(val: float) -> str:
    """백만원 단위 순매수 포맷."""
    if abs(val) >= 1000:
        return f"{val/1000:+.1f}십억"
    return f"{val:+.0f}백만"


def render_supply_demand(analysis_date: date, market):
    st.title(f"💰 수급 분석  |  {analysis_date}")
    st.caption(f"투자자별(외국인/기관/개인) 순매수 흐름 분석 (참고용)  —  {DISCLAIMER}")

    items = cached_supply_demand_top(analysis_date, limit=50)

    if not items:
        st.warning(
            f"**{analysis_date}** 수급 분석 데이터가 없습니다.\n\n"
            "분석 대상 종목 분석 완료 후 아래 배치 버튼을 눌러 수급 데이터를 수집하세요."
        )
        st.info("⚠️ pykrx로 KRX에 직접 조회합니다. 종목당 약 0.3초 소요 (80종목 ≈ 30초)")
        if st.button("▶ 수급 배치 분석 실행 (관심종목 + 상위 80개)", type="primary"):
            from app.services.supply_demand_analysis_service import run_supply_demand_batch
            with st.spinner("수급 데이터 수집 중... KRX 조회 중 (최대 3분 소요)"):
                result = run_supply_demand_batch(analysis_date, limit=80)
            if result.get("status") == "success":
                st.success(f"완료 — 성공 {result['success']}개 / 스킵 {result.get('skipped',0)}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류 발생"))
        return

    # ── KPI ──────────────────────────────────────────────────
    strong = [i for i in items if "매수" in i["supply_signal"]]
    weak   = [i for i in items if "매도" in i["supply_signal"]]
    avg_score = sum(i["supply_score"] for i in items) / len(items) if items else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card_html("분석 종목", f"{len(items)}개", "수급 데이터"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card_html("수급 강세", f"{len(strong)}개", "외국인/기관 매수우위", is_up=True), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card_html("수급 약세", f"{len(weak)}개", "외국인/기관 매도우위", is_up=False), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card_html("평균 점수", f"{avg_score:+.1f}pt", "수급 점수 평균",
                                   is_up=avg_score > 0 if avg_score != 0 else None), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 탭: 수급 강세 / 수급 약세 / 공매도 상위 ────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🟢 수급 강세 Top20", "🔴 수급 약세 Top20", "📉 공매도 상위", "🔍 종목 조회"]
    )

    def _supply_card(item: dict):
        sig   = item["supply_signal"]
        color = _SUPPLY_SIGNAL_COLOR.get(sig, "#8b949e")
        icon  = _SUPPLY_SIGNAL_ICON.get(sig, "▪️")
        score = item["supply_score"]
        code  = item["stock_code"]

        with st.expander(
            f"{icon} **{code}**   {sig}   점수 {score:+.1f}pt",
            expanded=False,
        ):
            # 지표 행
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("외국인(당일)", _net_buy_fmt(item["foreign_net_buy"]))
            c2.metric("기관(당일)",   _net_buy_fmt(item["institution_net_buy"]))
            c3.metric("개인(당일)",   _net_buy_fmt(item["individual_net_buy"]))
            c4.metric("공매도비중",    f"{item['short_sell_ratio']:.2f}%")

            st.markdown(
                f'<div style="display:flex;gap:20px;margin:6px 0;font-size:12px;">'
                f'<span>외국인 5일 <b style="color:{"#2ea043" if item["foreign_net_buy_5d"]>=0 else "#e5534b"}">'
                f'{_net_buy_fmt(item["foreign_net_buy_5d"])}</b></span>'
                f'<span>연속 <b>{item["foreign_buy_streak"]:+d}일</b></span>'
                f'<span>기관 5일 <b style="color:{"#2ea043" if item["institution_net_buy_5d"]>=0 else "#e5534b"}">'
                f'{_net_buy_fmt(item["institution_net_buy_5d"])}</b></span>'
                f'<span>연속 <b>{item["institution_buy_streak"]:+d}일</b></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_supply_score_bar(score), unsafe_allow_html=True)

            # AI 해설
            if item.get("ai_supply_summary"):
                st.markdown("**AI 수급 흐름 해설** *(참고용)*")
                st.markdown(
                    f'<div style="background:var(--secondary-background-color);'
                    f'border-left:3px solid {color};padding:10px 14px;'
                    f'border-radius:0 6px 6px 0;font-size:13px;line-height:1.7;">'
                    + (f'<b>📊 현황</b>  {item["ai_supply_summary"]}<br>' if item.get("ai_supply_summary") else "")
                    + (f'<b>💰 흐름</b>  {item["ai_supply_flow"]}<br>'   if item.get("ai_supply_flow") else "")
                    + (f'<b>⚠️ 주의</b>  {item["ai_supply_risk"]}'       if item.get("ai_supply_risk") else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )
            st.caption(f"최종 업데이트: {item.get('updated_at', '-')}  |  {DISCLAIMER}")

    with tab1:
        top_buy = sorted(items, key=lambda x: x["supply_score"], reverse=True)[:20]
        for item in top_buy:
            _supply_card(item)

    with tab2:
        top_sell = sorted(items, key=lambda x: x["supply_score"])[:20]
        for item in top_sell:
            _supply_card(item)

    with tab3:
        top_short = sorted(items, key=lambda x: x["short_sell_ratio"], reverse=True)[:20]
        st.caption("공매도 비중 상위 종목 (pykrx KRX 공매도 데이터 기준)")
        for item in top_short:
            if item["short_sell_ratio"] > 0:
                _supply_card(item)

    with tab4:
        st.markdown("##### 종목 코드로 수급 분석 조회·실행")
        col_in, col_btn = st.columns([3, 1])
        with col_in:
            search_code = st.text_input("종목코드", placeholder="005930", label_visibility="collapsed")
        with col_btn:
            do_analyze = st.button("수급 분석", type="primary")

        if search_code:
            sda = cached_supply_demand_stock(search_code.strip(), analysis_date)
            if sda:
                sig   = sda["supply_signal"]
                color = _SUPPLY_SIGNAL_COLOR.get(sig, "#8b949e")
                st.markdown(
                    f'<div style="background:var(--secondary-background-color);'
                    f'border:1px solid rgba(128,128,128,0.2);border-radius:10px;padding:16px 20px;">'
                    f'<div style="font-size:18px;font-weight:700;margin-bottom:10px;">'
                    f'{search_code}  '
                    f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
                    f'border-radius:4px;padding:2px 9px;font-size:13px;">{sig}</span></div>'
                    f'<div style="font-size:13px;color:var(--text-color);opacity:0.8;">'
                    f'수급 점수: <b>{sda["supply_score"]:+.1f}pt</b></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(_supply_score_bar(sda["supply_score"]), unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("외국인(당일)",  _net_buy_fmt(sda["foreign_net_buy"]))
                c2.metric("기관(당일)",    _net_buy_fmt(sda["institution_net_buy"]))
                c3.metric("공매도 비중",   f"{sda['short_sell_ratio']:.2f}%")

                st.markdown(
                    f'<div style="display:flex;gap:16px;margin:8px 0;font-size:12px;">'
                    f'<span>외국인 5일 {_net_buy_fmt(sda["foreign_net_buy_5d"])} / 연속 {sda["foreign_buy_streak"]:+d}일</span>'
                    f'<span>기관 5일 {_net_buy_fmt(sda["institution_net_buy_5d"])} / 연속 {sda["institution_buy_streak"]:+d}일</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if sda.get("ai_supply_summary"):
                    st.markdown("**AI 수급 해설** *(참고용)*")
                    st.info(
                        (f"📊 {sda['ai_supply_summary']}\n\n" if sda.get("ai_supply_summary") else "")
                        + (f"💰 {sda['ai_supply_flow']}\n\n"   if sda.get("ai_supply_flow") else "")
                        + (f"⚠️ {sda['ai_supply_risk']}"       if sda.get("ai_supply_risk") else "")
                    )
            elif do_analyze:
                from app.services.supply_demand_analysis_service import analyze_stock_supply_demand
                with st.spinner(f"{search_code} 수급 데이터 KRX 조회 중..."):
                    result = analyze_stock_supply_demand(search_code.strip(), analysis_date, with_ai=True)
                if result.get("status") == "success":
                    st.success(f"완료 — {result.get('supply_signal')} / 점수 {result.get('supply_score', 0):+.1f}pt")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(result.get("message", "수급 데이터 없음"))
            else:
                st.info(f"{search_code} 수급 분석 데이터가 없습니다. '수급 분석' 버튼을 눌러 조회하세요.")

    # ── 재실행 버튼 ─────────────────────────────────────────
    st.markdown("---")
    col_btn, col_info = st.columns([2, 8])
    with col_btn:
        if st.button("🔄 수급 배치 재실행", help="관심종목 + 분석점수 상위 종목 수급 재수집"):
            from app.services.supply_demand_analysis_service import run_supply_demand_batch
            with st.spinner("KRX 수급 데이터 수집 중... (최대 3분)"):
                result = run_supply_demand_batch(analysis_date, limit=80)
            if result.get("status") == "success":
                st.success(f"완료 — 성공 {result['success']}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류"))
    with col_info:
        upd = items[0].get("updated_at", "-") if items else "-"
        st.caption(f"마지막 분석: {upd}  |  {DISCLAIMER}")


# ── 테마 분석 ─────────────────────────────────────────────────

_THEME_SIGNAL_COLOR = {
    "매우 강세":  "#1a7f37",
    "강세 흐름":  "#2ea043",
    "순환매 관심":"#d29922",
    "혼조":       "#8b949e",
    "약세 흐름":  "#e5534b",
    "하락 주의":  "#b91c1c",
    # 레거시 호환
    "강세": "#2ea043",
    "약세": "#e5534b",
    "중립": "#8b949e",
}
_THEME_SIGNAL_ICON = {
    "매우 강세":  "🔥",
    "강세 흐름":  "🔺",
    "순환매 관심":"🔄",
    "혼조":       "▪️",
    "약세 흐름":  "🔻",
    "하락 주의":  "🚨",
    "강세": "🔺",
    "약세": "🔻",
    "중립": "▪️",
}


def _theme_bar_html(value: float, max_abs: float = 5.0) -> str:
    pct = min(abs(value) / max(max_abs, 0.01) * 100, 100)
    color = "#2ea043" if value >= 0 else "#e5534b"
    margin = "left:50%" if value >= 0 else f"left:calc(50% - {pct/2:.1f}%)"
    width = pct / 2
    return (
        f'<div style="position:relative;height:6px;background:rgba(128,128,128,0.15);'
        f'border-radius:3px;margin:4px 0;">'
        f'<div style="position:absolute;{margin};width:{width:.1f}%;height:100%;'
        f'background:{color};border-radius:3px;"></div></div>'
    )


def _signal_badge(signal: str) -> str:
    color = _THEME_SIGNAL_COLOR.get(signal, "#8b949e")
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'border-radius:4px;padding:1px 7px;font-size:11px;font-weight:600;">{signal}</span>'
    )


def _theme_expander_content(t: dict, color: str):
    r1d  = t["avg_return_1d"]
    r5d  = t["avg_return_5d"]
    r20d = t["avg_return_20d"]
    vol  = t.get("avg_volume_ratio", 0)
    bull_pct = t.get("bullish_ratio", 0)
    bear_pct = t.get("bearish_ratio", 0)
    mom  = t.get("momentum_avg", 0)
    trend= t.get("trend_avg", 0)
    risk = t.get("risk_avg", 0)

    # 수익률 지표
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("당일",  f"{r1d:+.2f}%")
    m2.metric("5일",   f"{r5d:+.2f}%")
    m3.metric("20일",  f"{r20d:+.2f}%")
    m4.metric("거래량비율", f"{vol:.2f}x", help="5일 평균 거래량 / 20일 평균 거래량")

    # 강세/약세 비율 + 점수
    st.markdown(
        f'<div style="display:flex;gap:20px;margin:8px 0;font-size:12px;flex-wrap:wrap;">'
        f'<span>강세 <b style="color:#2ea043">{bull_pct:.0f}%</b></span>'
        f'<span>약세 <b style="color:#e5534b">{bear_pct:.0f}%</b></span>'
        f'<span>모멘텀 <b>{mom:.1f}</b></span>'
        f'<span>추세 <b>{trend:.1f}</b></span>'
        f'<span>위험 <b style="color:{"#e5534b" if risk >= 15 else "var(--text-color)"}">{risk:.1f}</b></span>'
        f'<span>종목수 <b>{t["stock_count"]}개</b></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 스포트라이트 종목
    spt = {
        "strongest":      t.get("strongest_stock", {}),
        "weakest":        t.get("weakest_stock", {}),
        "volume_leader":  t.get("volume_leader", {}),
        "momentum_leader":t.get("momentum_leader", {}),
        "risk_warning":   t.get("risk_warning_stock", {}),
    }
    filled = {k: v for k, v in spt.items() if v and v.get("name")}
    if filled:
        spot_html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0;font-size:11px;">'
        labels = {
            "strongest":       ("🏆 강세대표", "return_5d", "%"),
            "weakest":         ("📉 약세대표", "return_5d", "%"),
            "volume_leader":   ("🔊 거래량", "volume_ratio", "x"),
            "momentum_leader": ("⚡ 모멘텀", "momentum_score", "pt"),
            "risk_warning":    ("⚠️ 위험", "risk_score", "pt"),
        }
        for k, info in filled.items():
            lbl, val_key, unit = labels[k]
            val = info.get(val_key, 0)
            spot_html += (
                f'<span style="background:var(--secondary-background-color);'
                f'border-radius:4px;padding:3px 8px;">'
                f'{lbl}: <b>{info["name"]}</b> '
                f'<span style="opacity:0.7">({val:+.2f}{unit})</span></span>'
            )
        spot_html += '</div>'
        st.markdown(spot_html, unsafe_allow_html=True)

    # AI 해설
    ai_fields = [
        ("ai_theme_summary",          "📊 현황"),
        ("ai_theme_flow",             "💰 수급 흐름"),
        ("ai_theme_volume_comment",   "🔊 거래량"),
        ("ai_theme_rotation_comment", "🔄 순환매"),
        ("ai_theme_risk",             "⚠️ 리스크"),
    ]
    has_ai = any(t.get(k) for k, _ in ai_fields)
    if has_ai:
        st.markdown("**AI 시장 흐름 분석** *(참고용 — 투자 권유 아님)*")
        lines = ""
        for field, label in ai_fields:
            val = t.get(field)
            if val:
                lines += f'<b>{label}</b>  {val}<br>'
        st.markdown(
            f'<div style="background:var(--secondary-background-color);'
            f'border-left:3px solid {color};padding:10px 14px;'
            f'border-radius:0 6px 6px 0;font-size:13px;line-height:1.7;">'
            f'{lines}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("AI 해설 없음 (OPENAI_API_KEY 미설정 또는 분석 전)")

    # 관련 종목 코드
    codes = t.get("stock_codes", [])[:12]
    if codes:
        st.caption("포함 종목: " + "  ·  ".join(codes)
                   + (f"  외 {len(t['stock_codes'])-12}개" if len(t.get("stock_codes",[])) > 12 else ""))


def _render_theme_list(theme_list: list[dict], section_key: str):
    for i, t in enumerate(theme_list):
        sig   = t["theme_signal"]
        color = _THEME_SIGNAL_COLOR.get(sig, "#8b949e")
        icon  = _THEME_SIGNAL_ICON.get(sig, "▪️")
        r5d   = t["avg_return_5d"]
        r1d   = t["avg_return_1d"]
        with st.expander(
            f"{icon} **{t['theme_name']}**   "
            f"5일 {r5d:+.2f}%  |  당일 {r1d:+.2f}%  |  {sig}",
            expanded=False,
        ):
            _theme_expander_content(t, color)


def render_theme_analysis(analysis_date: date, market):
    st.title(f"📈 테마 분석  |  {analysis_date}")
    st.caption(f"32개 시장 테마별 강세/약세 흐름 분석 (참고용)  —  {DISCLAIMER}")

    themes = cached_theme_analysis(analysis_date)

    if not themes:
        st.warning(
            f"**{analysis_date}** 테마 분석 데이터가 없습니다.\n\n"
            "먼저 종목 분석을 실행한 후 아래 버튼으로 테마 분석을 실행하세요."
        )
        if st.button("▶ 테마 분석 실행", type="primary"):
            from app.services.theme_analysis_service import run_theme_analysis
            with st.spinner("데이터 집계 + 뉴스 수집 + AI 분석 중... (최대 2분 소요)"):
                result = run_theme_analysis(analysis_date)
            if result.get("status") == "success":
                st.success(f"완료 — 테마 {result.get('themes', 0)}개 분석")
                st.cache_data.clear()
                st.rerun()
            elif result.get("status") == "no_data":
                st.warning("분석 데이터 없음 — 먼저 종목 분석을 실행하세요.")
            else:
                st.error(result.get("message", "오류 발생"))
        return

    # ── KPI 카드 ─────────────────────────────────────────────
    strong_themes   = [t for t in themes if t["theme_signal"] in ("매우 강세", "강세 흐름", "강세")]
    weak_themes     = [t for t in themes if t["theme_signal"] in ("약세 흐름", "하락 주의", "약세")]
    rotation_themes = [t for t in themes if t["theme_signal"] == "순환매 관심"]
    avg_r5 = sum(t["avg_return_5d"] for t in themes) / len(themes) if themes else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(_kpi_card_html("전체 테마", f"{len(themes)}개", "분류 완료"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card_html("강세 테마", f"{len(strong_themes)}개", "매우강세+강세흐름", is_up=True), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card_html("약세 테마", f"{len(weak_themes)}개", "약세흐름+하락주의", is_up=False), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card_html("순환매", f"{len(rotation_themes)}개", "순환매 관심 테마"), unsafe_allow_html=True)
    with k5:
        st.markdown(_kpi_card_html("5일 평균", f"{avg_r5:+.2f}%", "테마 평균 5일 수익률",
                                   is_up=avg_r5 > 0 if avg_r5 != 0 else None), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 전체 차트 ─────────────────────────────────────────────
    st.markdown('<p class="sec-hd">테마별 5일 평균 수익률</p>', unsafe_allow_html=True)
    chart_themes = sorted(themes, key=lambda x: x["avg_return_5d"])
    colors = [_THEME_SIGNAL_COLOR.get(t["theme_signal"], "#8b949e") for t in chart_themes]
    fig = go.Figure(go.Bar(
        x=[t["avg_return_5d"] for t in chart_themes],
        y=[t["theme_name"]    for t in chart_themes],
        orientation="h",
        marker_color=colors,
        text=[f"{t['avg_return_5d']:+.2f}%" for t in chart_themes],
        textposition="outside",
        textfont=dict(size=11),
    ))
    fig.update_layout(
        height=max(320, len(chart_themes) * 28),
        margin=dict(l=0, r=70, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
        xaxis=dict(zeroline=True, zerolinecolor="rgba(128,128,128,0.3)",
                   gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, key="theme_bar_5d")

    # ── 4개 섹션 ─────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔥 강세 Top10", "🔻 약세 Top10", "🔊 거래량급증", "🔄 순환매 관심"]
    )

    sorted_by_r5   = sorted(themes, key=lambda x: x["avg_return_5d"], reverse=True)
    sorted_by_vol  = sorted(themes, key=lambda x: x["avg_volume_ratio"], reverse=True)

    with tab1:
        top_bull = sorted_by_r5[:10]
        if top_bull:
            _render_theme_list(top_bull, "bull")
        else:
            st.caption("강세 테마 없음")

    with tab2:
        top_bear = sorted_by_r5[-10:][::-1]
        if top_bear:
            _render_theme_list(top_bear, "bear")
        else:
            st.caption("약세 테마 없음")

    with tab3:
        top_vol = [t for t in sorted_by_vol if t.get("avg_volume_ratio", 0) >= 1.2][:10]
        if top_vol:
            st.caption("5일 거래량 비율 1.2배 이상 테마")
            _render_theme_list(top_vol, "vol")
        else:
            st.caption("거래량 급증 테마 없음")

    with tab4:
        rot = [t for t in themes if t["theme_signal"] in ("순환매 관심", "혼조")]
        rot_sorted = sorted(rot, key=lambda x: x.get("avg_volume_ratio", 0), reverse=True)
        if rot_sorted:
            st.caption("거래량 증가 + 중립 흐름 — 자금 이동 가능성 테마")
            _render_theme_list(rot_sorted[:10], "rot")
        else:
            st.caption("순환매 관심 테마 없음")

    # ── 재실행 버튼 ───────────────────────────────────────────
    st.markdown("---")
    col_btn, col_info = st.columns([2, 8])
    with col_btn:
        if st.button("🔄 테마 분석 재실행", help="최신 데이터로 테마를 다시 집계합니다"):
            from app.services.theme_analysis_service import run_theme_analysis
            with st.spinner("데이터 집계 + 뉴스 수집 + AI 분석 중... (최대 2분 소요)"):
                result = run_theme_analysis(analysis_date)
            if result.get("status") == "success":
                st.success(f"완료 — 테마 {result.get('themes', 0)}개 분석")
                st.cache_data.clear()
                st.rerun()
            elif result.get("status") == "no_data":
                st.warning("분석 데이터 없음 — 먼저 종목 분석을 실행하세요.")
            else:
                st.error(result.get("message", "오류 발생"))
    with col_info:
        upd = themes[0].get("updated_at", "-") if themes else "-"
        st.caption(f"마지막 분석: {upd}  |  {DISCLAIMER}")


# ── 뉴스 감성 ──────────────────────────────────────────────────

_NEWS_SIGNAL_COLOR = {
    "강한 호재": "#2ea043",
    "호재 우세": "#57ab5a",
    "중립":      "#8b949e",
    "악재 우세": "#e09b3d",
    "강한 악재": "#e5534b",
}
_NEWS_SIGNAL_ICON = {
    "강한 호재": "🟢",
    "호재 우세": "🔵",
    "중립":      "⬜",
    "악재 우세": "🟠",
    "강한 악재": "🔴",
}
_SENTIMENT_ICON = {"호재": "✅", "악재": "❌", "중립": "➖"}


def _news_score_bar(score: float) -> str:
    pct = min(max((score + 100) / 200 * 100, 0), 100)
    color = "#2ea043" if score > 0 else ("#e5534b" if score < 0 else "#8b949e")
    return (
        f'<div style="background:var(--secondary-background-color);'
        f'border-radius:4px;height:8px;margin:6px 0;">'
        f'<div style="width:{pct:.1f}%;background:{color};height:8px;border-radius:4px;"></div>'
        f'</div><span style="font-size:11px;color:{color};">감성 점수 {score:+.1f}pt</span>'
    )


def render_news_sentiment(analysis_date: date, market):
    st.title(f"📰 뉴스 감성 분석  |  {analysis_date}")
    st.caption(f"구글/네이버/DART 뉴스 헤드라인 AI 감성 분류 (참고용)  —  {DISCLAIMER}")

    items = cached_news_top(analysis_date, limit=50)

    if not items:
        st.warning(
            f"**{analysis_date}** 뉴스 감성 데이터가 없습니다.\n\n"
            "배치 분석 버튼을 눌러 관심종목 + 상위 종목의 뉴스를 수집하고 감성 분석하세요."
        )
        st.info("📡 구글 뉴스 RSS + 네이버 파이낸스 + DART DB에서 헤드라인을 수집합니다.")
        if st.button("▶ 뉴스 감성 배치 분석 실행 (최대 80종목)", type="primary"):
            from app.services.news_analysis_service import run_news_batch
            with st.spinner("뉴스 수집 + AI 분류 중... (최대 5분 소요)"):
                result = run_news_batch(analysis_date, limit=80)
            if result.get("status") in ("success", "partial"):
                st.success(f"완료 — 성공 {result['success']}개 / 스킵 {result.get('skipped',0)}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류 발생"))
        return

    # ── KPI ──────────────────────────────────────────────────
    strong_pos = [i for i in items if i["news_sentiment_signal"] in ("강한 호재", "호재 우세")]
    strong_neg = [i for i in items if i["news_sentiment_signal"] in ("강한 악재", "악재 우세")]
    avg_score  = sum(i["news_sentiment_score"] for i in items) / len(items) if items else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card_html("분석 종목", f"{len(items)}개", "뉴스 감성 데이터"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card_html("호재 우세", f"{len(strong_pos)}개", "강한 호재 + 호재 우세", is_up=True), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card_html("악재 우세", f"{len(strong_neg)}개", "강한 악재 + 악재 우세", is_up=False), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card_html("평균 감성", f"{avg_score:+.1f}pt", "감성 점수 평균",
                                   is_up=avg_score > 0 if avg_score != 0 else None), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 탭 ───────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🟢 호재 우세 Top20", "🔴 악재 우세 Top20", "⬜ 중립", "🔍 종목 조회"]
    )

    def _news_card(item: dict):
        sig   = item["news_sentiment_signal"]
        color = _NEWS_SIGNAL_COLOR.get(sig, "#8b949e")
        icon  = _NEWS_SIGNAL_ICON.get(sig, "▪️")
        score = item["news_sentiment_score"]
        code  = item["stock_code"]
        total = item["total_news_count"] or 0

        with st.expander(
            f"{icon} **{code}**   {sig}   점수 {score:+.1f}pt   헤드라인 {total}건",
            expanded=False,
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("호재",  f"{item['positive_news_count']}건")
            c2.metric("악재",  f"{item['negative_news_count']}건")
            c3.metric("중립",  f"{item['neutral_news_count']}건")
            c4.metric("DART", f"{item['dart_news_count']}건")

            st.markdown(_news_score_bar(score), unsafe_allow_html=True)

            # AI 해설
            if item.get("ai_sentiment_summary"):
                st.markdown("**AI 감성 해설** *(참고용)*")
                st.markdown(
                    f'<div style="background:var(--secondary-background-color);'
                    f'border-left:3px solid {color};padding:10px 14px;'
                    f'border-radius:0 6px 6px 0;font-size:13px;line-height:1.7;">'
                    + (f'<b>📊 요약</b>  {item["ai_sentiment_summary"]}<br>' if item.get("ai_sentiment_summary") else "")
                    + (f'<b>🔑 이슈</b>  {item["ai_key_issues"]}<br>'        if item.get("ai_key_issues") else "")
                    + (f'<b>⚠️ 주의</b>  {item["ai_sentiment_risk"]}'        if item.get("ai_sentiment_risk") else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )

            # 헤드라인 목록
            if item.get("headlines_json"):
                try:
                    import json as _json
                    headlines = _json.loads(item["headlines_json"])
                    st.markdown("**수집 헤드라인**")
                    for h in headlines[:15]:
                        s_icon = _SENTIMENT_ICON.get(h.get("sentiment", "중립"), "➖")
                        src    = h.get("source", "?")
                        title  = h.get("title", "")
                        reason = h.get("reason", "")
                        st.markdown(
                            f'<div class="disc-row">{s_icon} [{src}] {title}'
                            + (f' <span style="color:#8b949e;font-size:11px;">— {reason}</span>' if reason else "")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                except Exception:
                    pass

            st.caption(f"최종 업데이트: {item.get('updated_at', '-')}  |  {DISCLAIMER}")

    with tab1:
        pos_items = [i for i in items if i["news_sentiment_signal"] in ("강한 호재", "호재 우세")]
        pos_items = sorted(pos_items, key=lambda x: x["news_sentiment_score"], reverse=True)[:20]
        if pos_items:
            for item in pos_items:
                _news_card(item)
        else:
            st.caption("호재 우세 종목 없음")

    with tab2:
        neg_items = [i for i in items if i["news_sentiment_signal"] in ("강한 악재", "악재 우세")]
        neg_items = sorted(neg_items, key=lambda x: x["news_sentiment_score"])[:20]
        if neg_items:
            for item in neg_items:
                _news_card(item)
        else:
            st.caption("악재 우세 종목 없음")

    with tab3:
        neu_items = [i for i in items if i["news_sentiment_signal"] == "중립"]
        neu_items = sorted(neu_items, key=lambda x: abs(x["news_sentiment_score"]), reverse=True)[:20]
        if neu_items:
            for item in neu_items:
                _news_card(item)
        else:
            st.caption("중립 종목 없음")

    with tab4:
        st.subheader("종목별 뉴스 감성 조회")
        col_code, col_btn = st.columns([3, 1])
        with col_code:
            search_code = st.text_input("종목 코드 (6자리)", placeholder="005930", key="news_search_code")
        with col_btn:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_single = st.button("조회", key="news_search_btn")

        if search_code and run_single:
            result = cached_news_stock(search_code.strip(), analysis_date)
            if result:
                _news_card(result)
            else:
                st.info("데이터 없음 — 아래 버튼으로 분석을 실행하세요.")
                if st.button(f"▶ {search_code} 뉴스 감성 분석 실행", key="news_single_run"):
                    from app.services.news_analysis_service import analyze_news_sentiment
                    with st.spinner("뉴스 수집 + AI 분류 중..."):
                        r = analyze_news_sentiment(search_code.strip(), analysis_date)
                    if r.get("status") == "success":
                        st.success(f"완료 — 호재 {r['positive']} / 악재 {r['negative']} / 중립 {r['neutral']}")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(r.get("message", "오류 발생"))

    # ── 재실행 버튼 ───────────────────────────────────────────
    st.markdown("---")
    col_btn2, col_info2 = st.columns([2, 8])
    with col_btn2:
        if st.button("🔄 뉴스 배치 재실행", help="관심종목 + 상위 80종목 뉴스 재수집"):
            from app.services.news_analysis_service import run_news_batch
            with st.spinner("뉴스 수집 + AI 분류 중... (최대 5분 소요)"):
                result = run_news_batch(analysis_date, limit=80)
            if result.get("status") in ("success", "partial"):
                st.success(f"완료 — 성공 {result['success']}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류 발생"))
    with col_info2:
        upd = items[0].get("updated_at", "-") if items else "-"
        st.caption(f"마지막 분석: {upd}  |  {DISCLAIMER}")


# ── 실적 분석 ──────────────────────────────────────────────────

_FUND_SIGNAL_COLOR = {
    "매우 우량": "#2ea043",
    "우량":      "#57ab5a",
    "보통":      "#8b949e",
    "주의":      "#e09b3d",
    "위험":      "#e5534b",
}
_FUND_SIGNAL_ICON = {
    "매우 우량": "🟢",
    "우량":      "🔵",
    "보통":      "⬜",
    "주의":      "🟠",
    "위험":      "🔴",
}


def _fmt_억(v) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 10000:
        return f"{v/10000:,.1f}조"
    return f"{v:,}억"


def _fund_score_bar(score: float) -> str:
    pct   = min(max((score + 100) / 200 * 100, 0), 100)
    color = "#2ea043" if score >= 35 else ("#e5534b" if score < -25 else "#e09b3d" if score < 5 else "#8b949e")
    return (
        f'<div style="background:var(--secondary-background-color);'
        f'border-radius:4px;height:8px;margin:6px 0;">'
        f'<div style="width:{pct:.1f}%;background:{color};height:8px;border-radius:4px;"></div>'
        f'</div><span style="font-size:11px;color:{color};">펀더멘털 점수 {score:+.1f}pt</span>'
    )


def _growth_color(v) -> str:
    if v is None:
        return "#8b949e"
    return "#2ea043" if v >= 0 else "#e5534b"


def render_fundamental(analysis_date: date, market):
    st.title(f"📊 실적 분석  |  {analysis_date}")
    st.caption(f"pykrx + 네이버 파이낸스 기반 펀더멘털 분석 (참고용)  —  {DISCLAIMER}")

    items = cached_fundamental_top(analysis_date, limit=50)

    if not items:
        st.warning(
            f"**{analysis_date}** 펀더멘털 분석 데이터가 없습니다.\n\n"
            "배치 분석 버튼을 눌러 관심종목 + 상위 종목의 실적 데이터를 수집하세요."
        )
        st.info("📡 pykrx(PER/PBR/EPS) + 네이버 파이낸스(매출/영업이익/순이익/ROE/부채비율)를 수집합니다.")
        if st.button("▶ 실적 배치 분석 실행 (최대 80종목)", type="primary"):
            from app.services.fundamental_analysis_service import run_fundamental_batch
            with st.spinner("재무 데이터 수집 + AI 분석 중... (최대 5분 소요)"):
                result = run_fundamental_batch(analysis_date, limit=80)
            if result.get("status") in ("success", "partial"):
                st.success(f"완료 — 성공 {result['success']}개 / 스킵 {result.get('skipped',0)}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류 발생"))
        return

    # ── KPI ──────────────────────────────────────────────────
    premium = [i for i in items if i["fundamental_signal"] in ("매우 우량", "우량")]
    risky   = [i for i in items if i["fundamental_signal"] in ("위험", "주의")]
    avg_sc  = sum(i["fundamental_score"] or 0 for i in items) / len(items)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(_kpi_card_html("분석 종목", f"{len(items)}개", "펀더멘털 데이터"), unsafe_allow_html=True)
    with k2:
        st.markdown(_kpi_card_html("우량 종목", f"{len(premium)}개", "매우 우량 + 우량", is_up=True), unsafe_allow_html=True)
    with k3:
        st.markdown(_kpi_card_html("위험 종목", f"{len(risky)}개", "위험 + 주의", is_up=False), unsafe_allow_html=True)
    with k4:
        st.markdown(_kpi_card_html("평균 점수", f"{avg_sc:+.1f}pt", "펀더멘털 점수 평균",
                                   is_up=avg_sc > 0 if avg_sc != 0 else None), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🟢 우량 Top20", "🔴 위험 Top20", "📈 성장률 순위", "🔍 종목 조회"]
    )

    def _fund_card(item: dict):
        sig   = item["fundamental_signal"]
        color = _FUND_SIGNAL_COLOR.get(sig, "#8b949e")
        icon  = _FUND_SIGNAL_ICON.get(sig, "▪️")
        score = item["fundamental_score"] or 0
        code  = item["stock_code"]

        with st.expander(
            f"{icon} **{code}**   {sig}   {score:+.1f}pt",
            expanded=False,
        ):
            # 재무 지표 행
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PER",    f"{item['per']:.1f}배"  if item['per']  else "N/A")
            c2.metric("PBR",    f"{item['pbr']:.2f}배"  if item['pbr']  else "N/A")
            c3.metric("ROE",    f"{item['roe']:.1f}%"   if item['roe']  else "N/A")
            c4.metric("부채비율", f"{item['debt_ratio']:.1f}%" if item['debt_ratio'] else "N/A")

            # 성장률 배지
            def _badge(label: str, val) -> str:
                if val is None:
                    return f'<span style="background:#2d333b;padding:3px 8px;border-radius:4px;font-size:12px;">{label}: N/A</span>'
                c = _growth_color(val)
                arrow = "▲" if val >= 0 else "▼"
                return (
                    f'<span style="background:#2d333b;padding:3px 8px;border-radius:4px;'
                    f'font-size:12px;color:{c};">{label}: {arrow}{abs(val):.1f}%</span>'
                )

            st.markdown(
                '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0;">'
                + _badge("매출 성장", item["revenue_growth"])
                + _badge("영업이익 성장", item["operating_income_growth"])
                + _badge("순이익 성장", item["net_income_growth"])
                + _badge("EPS 성장", item["eps_growth"])
                + "</div>",
                unsafe_allow_html=True,
            )

            # 연간 재무 추이
            rev_c   = _fmt_억(item["revenue_current"])
            rev_p   = _fmt_억(item["revenue_prev1"])
            opi_c   = _fmt_억(item["op_income_current"])
            opi_p   = _fmt_억(item["op_income_prev1"])
            net_c   = _fmt_억(item["net_income_current"])
            net_p   = _fmt_억(item["net_income_prev1"])
            eps_val = item["eps"]
            eps_str = f"{eps_val:,}원" if eps_val else "N/A"
            st.markdown(
                f'<div style="display:flex;gap:20px;margin:6px 0;font-size:12px;flex-wrap:wrap;">'
                f'<span>매출 <b>{rev_c}</b> ← {rev_p}</span>'
                f'<span>영업이익 <b>{opi_c}</b> ← {opi_p}</span>'
                f'<span>순이익 <b>{net_c}</b> ← {net_p}</span>'
                f'<span>EPS <b>{eps_str}</b></span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown(_fund_score_bar(score), unsafe_allow_html=True)

            # 세부 점수
            st.markdown(
                f'<div style="display:flex;gap:16px;font-size:11px;color:#8b949e;margin:4px 0;">'
                f'<span>ROE점수 {item["roe_score"] or 0:+.0f}</span>'
                f'<span>부채안전 {item["debt_risk_score"] or 0:+.0f}</span>'
                f'<span>밸류 {item["valuation_score"] or 0:+.0f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # AI 해설
            if item.get("ai_fundamental_summary"):
                st.markdown("**AI 실적 해설** *(참고용)*")
                st.markdown(
                    f'<div style="background:var(--secondary-background-color);'
                    f'border-left:3px solid {color};padding:10px 14px;'
                    f'border-radius:0 6px 6px 0;font-size:13px;line-height:1.7;">'
                    + (f'<b>📊 종합</b>  {item["ai_fundamental_summary"]}<br>' if item.get("ai_fundamental_summary") else "")
                    + (f'<b>📈 성장</b>  {item["ai_growth_comment"]}<br>'      if item.get("ai_growth_comment") else "")
                    + (f'<b>💹 밸류</b>  {item["ai_valuation_comment"]}<br>'   if item.get("ai_valuation_comment") else "")
                    + (f'<b>⚠️ 리스크</b>  {item["ai_risk_comment"]}'          if item.get("ai_risk_comment") else "")
                    + '</div>',
                    unsafe_allow_html=True,
                )

            st.caption(
                f"데이터 소스: {item.get('data_source','-')}  |  "
                f"업데이트: {item.get('updated_at','-')}  |  {DISCLAIMER}"
            )

    with tab1:
        good = [i for i in items if i["fundamental_signal"] in ("매우 우량", "우량")]
        good = sorted(good, key=lambda x: x["fundamental_score"] or 0, reverse=True)[:20]
        if good:
            for item in good:
                _fund_card(item)
        else:
            st.caption("우량 종목 없음")

    with tab2:
        bad = [i for i in items if i["fundamental_signal"] in ("위험", "주의")]
        bad = sorted(bad, key=lambda x: x["fundamental_score"] or 0)[:20]
        if bad:
            for item in bad:
                _fund_card(item)
        else:
            st.caption("위험 종목 없음")

    with tab3:
        st.subheader("영업이익 성장률 순위")
        growth_items = [
            i for i in items
            if i.get("operating_income_growth") is not None
        ]
        growth_items = sorted(growth_items, key=lambda x: x["operating_income_growth"], reverse=True)[:20]
        if growth_items:
            rows = []
            for it in growth_items:
                rows.append({
                    "종목코드": it["stock_code"],
                    "시그널": it["fundamental_signal"],
                    "매출성장(%)": it["revenue_growth"],
                    "영업이익성장(%)": it["operating_income_growth"],
                    "순이익성장(%)": it["net_income_growth"],
                    "ROE(%)": it["roe"],
                    "PER(배)": it["per"],
                    "부채비율(%)": it["debt_ratio"],
                    "점수": it["fundamental_score"],
                })
            st.dataframe(
                rows,
                use_container_width=True,
                column_config={
                    "영업이익성장(%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "매출성장(%)":     st.column_config.NumberColumn(format="%.1f%%"),
                    "순이익성장(%)":   st.column_config.NumberColumn(format="%.1f%%"),
                    "ROE(%)":         st.column_config.NumberColumn(format="%.1f%%"),
                    "PER(배)":        st.column_config.NumberColumn(format="%.1f배"),
                    "부채비율(%)":    st.column_config.NumberColumn(format="%.1f%%"),
                    "점수":           st.column_config.NumberColumn(format="%+.1f"),
                },
            )
        else:
            st.caption("성장률 데이터 없음")

    with tab4:
        st.subheader("종목별 실적 분석 조회")
        col_code, col_btn = st.columns([3, 1])
        with col_code:
            f_code = st.text_input("종목 코드 (6자리)", placeholder="005930", key="fund_search_code")
        with col_btn:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_f = st.button("조회", key="fund_search_btn")

        if f_code and run_f:
            result = cached_fundamental_stock(f_code.strip(), analysis_date)
            if result:
                _fund_card(result)
            else:
                st.info("데이터 없음 — 아래 버튼으로 분석을 실행하세요.")
                if st.button(f"▶ {f_code} 실적 분석 실행", key="fund_single_run"):
                    from app.services.fundamental_analysis_service import analyze_fundamental
                    with st.spinner("재무 데이터 수집 중..."):
                        r = analyze_fundamental(f_code.strip(), analysis_date)
                    if r.get("status") == "success":
                        st.success(
                            f"완료 — 점수 {r['fundamental_score']:+.1f}pt "
                            f"({r['fundamental_signal']})"
                        )
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(r.get("message", "오류 발생"))

    st.markdown("---")
    col_btn2, col_info2 = st.columns([2, 8])
    with col_btn2:
        if st.button("🔄 실적 배치 재실행", help="관심종목 + 상위 80종목 실적 재수집"):
            from app.services.fundamental_analysis_service import run_fundamental_batch
            with st.spinner("재무 데이터 수집 중... (최대 5분 소요)"):
                result = run_fundamental_batch(analysis_date, limit=80)
            if result.get("status") in ("success", "partial"):
                st.success(f"완료 — 성공 {result['success']}개")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("message", "오류 발생"))
    with col_info2:
        upd = items[0].get("updated_at", "-") if items else "-"
        st.caption(f"마지막 분석: {upd}  |  {DISCLAIMER}")


# ── 메인 ──────────────────────────────────────────────────────

# ── 시장 종합 흐름 ────────────────────────────────────────────

def render_market_flow(analysis_date: date, market=None):
    """9개 섹션 한눈에 보기 — 외국인·기관 수급 / 뉴스 / 주도주 / 테마 순환 / 위험·패턴."""
    st.title(f"🌊 시장 종합 흐름  |  {analysis_date}")
    st.caption(
        f"외국인·기관 수급 / 뉴스 감성 / 주도주 / 거래대금 / 테마 순환 / 위험·차트패턴 종합 (참고용)  —  {DISCLAIMER}"
    )

    # ── 공통 헬퍼 ─────────────────────────────────────────────
    CARD = (
        "background:var(--secondary-background-color);"
        "border:1px solid rgba(128,128,128,0.2);border-radius:10px;"
        "padding:14px 16px;margin-bottom:4px;"
    )
    ITEM = "font-size:12px;padding:5px 2px;border-bottom:1px solid rgba(128,128,128,0.10);line-height:1.5;"
    EMPTY = "font-size:12px;opacity:0.45;text-align:center;padding:30px 6px;"

    def _net_fmt(v: float) -> str:
        if abs(v) >= 1_000:
            return f"{v / 1_000:+.1f}십억"
        return f"{v:+.0f}백만"

    def _tv_fmt(v) -> str:
        if v is None:
            return "-"
        v = float(v)
        if v >= 1e12:
            return f"{v / 1e12:.1f}조"
        if v >= 1e8:
            return f"{v / 1e8:.0f}억"
        return f"{v / 1e4:.0f}만"

    def _card_open(icon, label, color):
        st.markdown(
            f'<div style="{CARD}">'
            f'<p style="font-size:13px;font-weight:700;color:{color};margin:0 0 10px;">'
            f'{icon} {label}</p>',
            unsafe_allow_html=True,
        )

    def _card_close():
        st.markdown("</div>", unsafe_allow_html=True)

    def _row(rank, left, right_html):
        st.markdown(
            f'<div style="{ITEM}">'
            f'<span style="opacity:0.45;font-size:11px;margin-right:4px;">{rank}.</span>'
            f'<b>{left}</b>'
            f'<span style="float:right;font-size:11px;">{right_html}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def _empty(msg="데이터 없음"):
        st.markdown(f'<div style="{EMPTY}">{msg}</div>', unsafe_allow_html=True)

    # ── Row 1: 외국인 수급 / 기관 수급 / 시장 주도주 ─────────
    r1c1, r1c2, r1c3 = st.columns(3)

    # ① 외국인 수급 TOP
    with r1c1:
        _card_open("🌍", "외국인 수급 TOP", "#57ab5a")
        items = cached_market_flow_foreign_top(analysis_date, limit=10)
        if not items:
            _empty("수급 분석 데이터 없음<br>(수급 분석 배치 실행 필요)")
        else:
            for i, it in enumerate(items, 1):
                v = it["foreign_net_buy"]
                streak = it["foreign_buy_streak"]
                streak_txt = (
                    f"<span style='color:#57ab5a;'> ▲{streak}연속</span>" if streak > 0
                    else f"<span style='color:#e5534b;'> ▼{abs(streak)}연속</span>" if streak < 0
                    else ""
                )
                color = "#57ab5a" if v >= 0 else "#e5534b"
                _row(
                    i, it["stock_code"],
                    f'<span style="color:{color};">{_net_fmt(v)}</span>{streak_txt}',
                )
        _card_close()

    # ② 기관 수급 TOP
    with r1c2:
        _card_open("🏛️", "기관 수급 TOP", "#6cb6ff")
        items = cached_market_flow_institution_top(analysis_date, limit=10)
        if not items:
            _empty("수급 분석 데이터 없음<br>(수급 분석 배치 실행 필요)")
        else:
            for i, it in enumerate(items, 1):
                v = it["institution_net_buy"]
                streak = it["institution_buy_streak"]
                streak_txt = (
                    f"<span style='color:#6cb6ff;'> ▲{streak}연속</span>" if streak > 0
                    else f"<span style='color:#e5534b;'> ▼{abs(streak)}연속</span>" if streak < 0
                    else ""
                )
                color = "#6cb6ff" if v >= 0 else "#e5534b"
                _row(
                    i, it["stock_code"],
                    f'<span style="color:{color};">{_net_fmt(v)}</span>{streak_txt}',
                )
        _card_close()

    # ③ 시장 주도주
    with r1c3:
        _card_open("🚀", "시장 주도주", "#f0883e")
        leaders = cached_market_flow_leaders(analysis_date, limit=10)
        if not leaders:
            _empty("주도주 데이터 없음<br>(주도주 배치 실행 필요)")
        else:
            _LEADER_COLOR = {
                "시장 주도주": "#f0883e",
                "주도 후보":  "#d29922",
                "관심 종목":  "#388bfd",
                "일반":       "#8b949e",
            }
            for i, it in enumerate(leaders, 1):
                name = (it.get("stock_name") or it["stock_code"])[:6]
                score = it.get("market_leader_score") or 0
                sig = it.get("leader_signal") or "일반"
                color = _LEADER_COLOR.get(sig, "#8b949e")
                _row(
                    i,
                    f'{it["stock_code"]} <span style="opacity:0.6;font-size:11px;">{name}</span>',
                    f'<span style="color:{color};">{score:.0f}점  {sig}</span>',
                )
        _card_close()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Row 2: 뉴스 호재 / 뉴스 악재 / 거래대금 급증 ─────────
    r2c1, r2c2, r2c3 = st.columns(3)

    # ④ 뉴스 호재 TOP
    with r2c1:
        _card_open("📰", "뉴스 호재 TOP", "#2ea043")
        news_pos = [
            n for n in cached_market_flow_news(analysis_date, limit=50)
            if n.get("news_sentiment_signal") in ("강한 호재", "호재 우세")
        ]
        news_pos = sorted(news_pos, key=lambda x: x["news_sentiment_score"], reverse=True)[:10]
        if not news_pos:
            _empty("뉴스 감성 데이터 없음<br>(뉴스 배치 분석 실행 필요)")
        else:
            _NEWS_ICON = {"강한 호재": "🟢", "호재 우세": "🔵"}
            for i, it in enumerate(news_pos, 1):
                sig = it["news_sentiment_signal"]
                score = it["news_sentiment_score"]
                icon = _NEWS_ICON.get(sig, "")
                _row(
                    i, it["stock_code"],
                    f'<span style="color:#2ea043;">{icon} {score:+.0f}pt</span>',
                )
        _card_close()

    # ⑤ 뉴스 악재 TOP
    with r2c2:
        _card_open("📰", "뉴스 악재 TOP", "#e5534b")
        news_neg = cached_market_flow_news_negative(analysis_date, limit=10)
        if not news_neg:
            _empty("뉴스 악재 데이터 없음<br>(뉴스 배치 분석 실행 필요)")
        else:
            _NEG_ICON = {"강한 악재": "🔴", "악재 우세": "🟠"}
            for i, it in enumerate(news_neg, 1):
                sig = it["news_sentiment_signal"]
                score = it["news_sentiment_score"]
                icon = _NEG_ICON.get(sig, "")
                cnt = it["negative_news_count"]
                _row(
                    i, it["stock_code"],
                    f'<span style="color:#e5534b;">{icon} {score:+.0f}pt  {cnt}건</span>',
                )
        _card_close()

    # ⑥ 거래대금 급증 종목
    with r2c3:
        _card_open("💸", "거래대금 급증 종목", "#d29922")
        tv_items = cached_market_flow_trading_value(analysis_date, limit=10)
        if not tv_items:
            _empty("거래대금 데이터 없음<br>(주도주 배치 실행 필요)")
        else:
            for i, it in enumerate(tv_items, 1):
                vs_avg = it.get("trading_value_vs_avg5")
                tv = it.get("trading_value")
                name = (it.get("stock_name") or it["stock_code"])[:5]
                color = "#d29922" if (vs_avg or 0) >= 0 else "#e5534b"
                vs_txt = f" {vs_avg:+.0f}%" if vs_avg is not None else ""
                _row(
                    i,
                    f'{it["stock_code"]} <span style="opacity:0.6;font-size:11px;">{name}</span>',
                    f'<span style="color:{color};">{_tv_fmt(tv)}<span style="font-size:10px;">{vs_txt}</span></span>',
                )
        _card_close()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Row 3: 테마 순환 / 위험도 높은 종목 / 차트 패턴 ─────────
    r3c1, r3c2, r3c3 = st.columns(3)

    # ⑦ 테마 순환 흐름
    with r3c1:
        _card_open("🔄", "테마 순환 흐름", "#bc8cff")
        _rotation_summary, rotation_results = cached_market_flow_rotation(analysis_date)
        _ROT_COLOR = {
            "순환매 유입": "#2ea043",
            "유지 강세":  "#57ab5a",
            "횡보":       "#8b949e",
            "이탈":       "#e09b3d",
            "약세 지속":  "#e5534b",
        }
        if not rotation_results:
            _empty("테마 순환 데이터 없음<br>(테마 순환 배치 실행 필요)")
        else:
            for i, it in enumerate(rotation_results[:10], 1):
                sig = it.get("rotation_signal") or "횡보"
                score = it.get("theme_rotation_score") or 0
                color = _ROT_COLOR.get(sig, "#8b949e")
                theme = (it.get("theme_name") or "-")[:10]
                rank_chg = it.get("rank_change") or 0
                rank_txt = (
                    f"<span style='color:#2ea043;'>▲{rank_chg}</span>" if rank_chg > 0
                    else f"<span style='color:#e5534b;'>▼{abs(rank_chg)}</span>" if rank_chg < 0
                    else ""
                )
                _row(
                    i, theme,
                    f'<span style="color:{color};">{sig}</span>  {rank_txt}',
                )
        _card_close()

    # ⑧ 위험도 높은 종목
    with r3c2:
        _card_open("⚠️", "위험도 높은 종목", "#e5534b")
        _RISK_COLOR = {
            "과열주의": "#b91c1c",
            "고위험":   "#e5534b",
            "주의":     "#e09b3d",
            "보통":     "#8b949e",
            "안정":     "#2ea043",
        }
        risk_items = cached_market_flow_risk(analysis_date, limit=10)
        if not risk_items:
            _empty("위험도 데이터 없음<br>(위험도 배치 실행 필요)")
        else:
            for i, it in enumerate(risk_items, 1):
                grade = it.get("risk_grade") or "보통"
                score = it.get("total_risk_score") or 0
                color = _RISK_COLOR.get(grade, "#8b949e")
                factors = it.get("risk_factors") or []
                top_factor = factors[0] if factors else ""
                _row(
                    i, it["stock_code"],
                    f'<span style="color:{color};">{grade}  {score:.0f}pt</span>',
                )
        _card_close()

    # ⑨ 차트 패턴 감지 종목
    with r3c3:
        _card_open("📊", "차트 패턴 감지 종목", "#58a6ff")
        _CHART_COLOR = {
            "강한상승패턴": "#2ea043",
            "상승패턴":    "#57ab5a",
            "중립":        "#8b949e",
            "약세":        "#e09b3d",
            "하락주의":    "#e5534b",
        }
        chart_items = cached_market_flow_chart(analysis_date, limit=10)
        if not chart_items:
            _empty("차트 패턴 데이터 없음<br>(차트 패턴 배치 실행 필요)")
        else:
            for i, it in enumerate(chart_items, 1):
                sig = it.get("chart_signal") or "중립"
                score = it.get("pattern_score") or 0
                color = _CHART_COLOR.get(sig, "#8b949e")
                patterns = it.get("pattern_descriptions") or ""
                short_p = (patterns.split("|")[0].strip()[:12]) if patterns else ""
                _row(
                    i,
                    f'{it["stock_code"]} <span style="opacity:0.55;font-size:10px;">{short_p}</span>',
                    f'<span style="color:{color};">{sig}</span>',
                )
        _card_close()

    st.markdown("---")
    st.caption(f"⚠️ 위 데이터는 참고용이며 투자 권유가 아닙니다.  |  {DISCLAIMER}")


def main():
    page, analysis_date, market_filter = render_sidebar()

    # 사이드바 전체 분석 버튼 처리
    if st.session_state.pop("run_all_pending", False):
        run_date    = st.session_state.pop("run_all_date", analysis_date)
        inc_collect = st.session_state.pop("run_all_include_collect", False)
        title_txt   = "처음부터 전체 실행" if inc_collect else "분석만 재실행"
        st.title(f"🚀 {title_txt}  |  {run_date}")
        results = _run_all_analyses(run_date, include_collect=inc_collect)
        label_map = {
            "collect_stocks":  "📋 종목수집",
            "collect_indices": "📉 지수수집",
            "collect_prices":  "📈 시세수집",
            "base_analysis":   "🔬 기본분석",
            "supply":          "💰 수급",
            "theme":           "📈 테마",
            "news":            "📰 뉴스",
            "fundamental":     "📊 실적",
            "ai_report":       "🤖 AI",
        }
        ok_parts, fail_parts = [], []
        for key, label in label_map.items():
            res = results.get(key)
            if res is None:
                continue
            status = res.get("status", "error")
            if status in ("success", "partial"):
                cnt = res.get("success", res.get("themes", res.get("count", "")))
                ok_parts.append(f"{label} ✅" + (f" {cnt}건" if cnt else ""))
            else:
                msg = res.get("message", "오류")[:40]
                fail_parts.append(f"{label} ❌ ({msg})")
        if ok_parts:
            st.success("완료: " + "  |  ".join(ok_parts))
        if fail_parts:
            st.warning("실패: " + "  |  ".join(fail_parts))
        st.cache_data.clear()
        st.stop()

    if page == "🏠 대시보드":
        render_home(analysis_date, market_filter)
    elif page == "🌊 시장 종합 흐름":
        render_market_flow(analysis_date, market_filter)
    elif page == "📈 테마 분석":
        render_theme_analysis(analysis_date, market_filter)
    elif page == "💰 수급 분석":
        render_supply_demand(analysis_date, market_filter)
    elif page == "📰 뉴스 감성":
        render_news_sentiment(analysis_date, market_filter)
    elif page == "📊 실적 분석":
        render_fundamental(analysis_date, market_filter)
    elif page == "⭐ 관심 종목":
        render_watchlist(analysis_date)
    elif page == "🔍 종목 검색":
        render_stock_search(analysis_date)
    elif page == "🤖 AI 분석":
        render_ai_analysis(analysis_date, market_filter)
    elif page == "📋 최신 리포트":
        render_report()
    elif page == "⚙️ 스케줄러":
        render_scheduler()

    st.markdown("---")
    st.caption(DISCLAIMER)


if __name__ == "__main__":
    main()
