"""
리포트 서비스 - 분석 결과를 Markdown/HTML 리포트로 생성하고 DB에 저장합니다.
"""
import csv
import io
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import func as sqlfunc, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.disclosure import Disclosure
from app.models.market import MarketIndex
from app.models.report import DailyMarketReport
from app.models.stock import Stock
from app.models.watchlist import WatchlistGroup, WatchlistItem
from app.services.analysis_service import get_analysis_results, get_analysis_summary, get_high_volume_stocks

logger = logging.getLogger(__name__)

DISCLAIMER = "투자 판단은 사용자 본인 책임이며, 본 결과는 참고용입니다."
_DISCLAIMER_MD = f"> ⚠️ {DISCLAIMER}"

_SIGNAL_ORDER = ["강세 관심", "추세 유지", "관망", "약세 주의", "하락 위험"]


# ── 데이터 수집 헬퍼 ─────────────────────────────────────────────

def _get_market_indices(report_date: date, session) -> list[dict]:
    results = []
    for code, name in [("KS11", "KOSPI"), ("KQ11", "KOSDAQ")]:
        q = (
            select(MarketIndex)
            .where(MarketIndex.index_code == code, MarketIndex.trade_date <= report_date)
            .order_by(MarketIndex.trade_date.desc())
            .limit(1)
        )
        row = session.execute(q).scalar_one_or_none()
        if row:
            results.append({
                "name": name,
                "close_value": float(row.close_value) if row.close_value else None,
                "change_rate": float(row.change_rate) if row.change_rate else None,
                "change_value": float(row.change_value) if row.change_value else None,
            })
    return results


def _get_sector_analysis(report_date: date, session) -> tuple[list[dict], list[dict]]:
    q = (
        select(
            Stock.sector,
            sqlfunc.count().label("count"),
            sqlfunc.avg(StockAnalysisResult.bullish_score).label("avg_bullish"),
            sqlfunc.avg(StockAnalysisResult.bearish_score).label("avg_bearish"),
            sqlfunc.avg(StockAnalysisResult.daily_return).label("avg_daily_return"),
            sqlfunc.avg(StockAnalysisResult.return_5d).label("avg_return_5d"),
        )
        .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code)
        .where(
            StockAnalysisResult.analysis_date == report_date,
            Stock.sector.isnot(None),
            Stock.sector != "",
            Stock.sector != "nan",
        )
        .group_by(Stock.sector)
        .having(sqlfunc.count() >= 3)
    )
    rows = session.execute(q).all()
    sectors = [
        {
            "sector": r.sector,
            "count": r.count,
            "avg_bullish": float(r.avg_bullish) if r.avg_bullish else 0.0,
            "avg_bearish": float(r.avg_bearish) if r.avg_bearish else 0.0,
            "avg_daily_return": float(r.avg_daily_return) if r.avg_daily_return else 0.0,
            "avg_return_5d": float(r.avg_return_5d) if r.avg_return_5d else 0.0,
        }
        for r in rows
    ]
    top = sorted(sectors, key=lambda x: x["avg_bullish"], reverse=True)[:5]
    bottom = sorted(sectors, key=lambda x: x["avg_bearish"], reverse=True)[:5]
    return top, bottom


def _get_disclosure_stocks(report_date: date, session) -> list[dict]:
    q = (
        select(Disclosure, Stock.stock_name)
        .join(Stock, Disclosure.stock_code == Stock.stock_code, isouter=True)
        .where(Disclosure.report_date == report_date)
        .order_by(Disclosure.id.desc())
        .limit(20)
    )
    rows = session.execute(q).all()
    return [
        {
            "stock_code": r.Disclosure.stock_code or "-",
            "stock_name": r.stock_name or "-",
            "title": r.Disclosure.title,
            "disclosure_type": r.Disclosure.disclosure_type or "-",
            "risk_level": r.Disclosure.risk_level or "-",
            "url": r.Disclosure.url or "",
        }
        for r in rows
    ]


def _get_watchlist_summary(report_date: date, session) -> list[dict]:
    groups = session.execute(select(WatchlistGroup).order_by(WatchlistGroup.id)).scalars().all()
    result = []
    for group in groups:
        items_q = (
            select(WatchlistItem, StockAnalysisResult, Stock.stock_name, Stock.market, Stock.sector)
            .join(Stock, WatchlistItem.stock_code == Stock.stock_code, isouter=True)
            .join(
                StockAnalysisResult,
                (WatchlistItem.stock_code == StockAnalysisResult.stock_code)
                & (StockAnalysisResult.analysis_date == report_date),
                isouter=True,
            )
            .where(WatchlistItem.group_id == group.id)
        )
        items = session.execute(items_q).all()
        if not items:
            continue
        stocks = []
        for item in items:
            ar = item.StockAnalysisResult
            stocks.append({
                "stock_code": item.WatchlistItem.stock_code,
                "stock_name": item.stock_name or "-",
                "market": item.market or "-",
                "sector": item.sector or "-",
                "memo": item.WatchlistItem.memo or "",
                "final_signal": ar.final_signal if ar else "-",
                "daily_return": float(ar.daily_return) if ar and ar.daily_return else None,
                "return_5d": float(ar.return_5d) if ar and ar.return_5d else None,
                "return_20d": float(ar.return_20d) if ar and ar.return_20d else None,
                "bullish_score": float(ar.bullish_score) if ar and ar.bullish_score else None,
                "bearish_score": float(ar.bearish_score) if ar and ar.bearish_score else None,
                "rsi14": float(ar.rsi14) if ar and ar.rsi14 else None,
                "signal_reason": ar.signal_reason if ar else None,
            })
        result.append({
            "group_name": group.group_name,
            "description": group.description or "",
            "stocks": stocks,
        })
    return result


# ── Markdown 빌더 ────────────────────────────────────────────────

def _fmt_pct(v) -> str:
    return f"{float(v):+.2f}%" if v is not None else "-"

def _fmt_f(v, dec=1) -> str:
    return f"{float(v):.{dec}f}" if v is not None else "-"


def _build_markdown(
    report_date: date,
    indices: list[dict],
    summary: dict,
    sector_top: list[dict],
    sector_bottom: list[dict],
    bullish_top: list[dict],
    bearish_top: list[dict],
    high_volume: list[dict],
    disclosures: list[dict],
    watchlist: list[dict],
    risk_stocks: list[dict],
) -> str:
    lines = [
        f"# 📊 일일 시장 분석 리포트 - {report_date}",
        "",
        _DISCLAIMER_MD,
        "",
        "## 시장 요약",
        "",
    ]
    for idx in indices:
        cr = _fmt_pct(idx.get("change_rate"))
        cv = f"{idx['close_value']:,.2f}" if idx.get("close_value") else "-"
        lines.append(f"- **{idx['name']}**: {cv} ({cr})")

    total = summary.get("total", 0)
    bullish_cnt = summary.get("강세 관심", 0)
    bearish_cnt = summary.get("하락 위험", 0) + summary.get("약세 주의", 0)

    lines += [
        "",
        f"**분석 종목 수**: {total}개 | **강세 관심**: {bullish_cnt}개 | **약세/위험**: {bearish_cnt}개",
        "",
        "| 시그널 | 종목 수 |",
        "| --- | --- |",
    ]
    for sig in _SIGNAL_ORDER:
        lines.append(f"| {sig} | {summary.get(sig, 0)}개 |")

    lines += ["", "---", ""]

    # 강세 업종
    if sector_top:
        lines += [
            "## 📈 강세 업종 TOP 5",
            "",
            "| 업종 | 종목 수 | 평균 당일 등락 | 평균 5일 수익률 | 강세 점수 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for s in sector_top:
            lines.append(
                f"| {s['sector']} | {s['count']}개 | {_fmt_pct(s['avg_daily_return'])} "
                f"| {_fmt_pct(s['avg_return_5d'])} | {_fmt_f(s['avg_bullish'])} |"
            )
        lines += [""]

    # 약세 업종
    if sector_bottom:
        lines += [
            "## 📉 약세 업종 TOP 5",
            "",
            "| 업종 | 종목 수 | 평균 당일 등락 | 평균 5일 수익률 | 약세 점수 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for s in sector_bottom:
            lines.append(
                f"| {s['sector']} | {s['count']}개 | {_fmt_pct(s['avg_daily_return'])} "
                f"| {_fmt_pct(s['avg_return_5d'])} | {_fmt_f(s['avg_bearish'])} |"
            )
        lines += ["", "---", ""]

    # 강세 TOP 20
    lines += [
        "## 🔥 강세 관심 TOP 20",
        "",
        "| 순위 | 종목코드 | 종목명 | 시장 | 업종 | 당일 | 5일 | 20일 | 거래량비 | RSI | 강세점수 | 시그널 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(bullish_top, 1):
        vr = f"{r['volume_ratio_5d']:.1f}x" if r.get("volume_ratio_5d") is not None else "-"
        lines.append(
            f"| {i} | {r['stock_code']} | {r.get('stock_name','-')} | {r.get('market','-')} | "
            f"{r.get('sector') or '-'} | {_fmt_pct(r.get('daily_return'))} | "
            f"{_fmt_pct(r.get('return_5d'))} | {_fmt_pct(r.get('return_20d'))} | "
            f"{vr} | {_fmt_f(r.get('rsi14'))} | {_fmt_f(r.get('bullish_score'))} | {r.get('final_signal','-')} |"
        )

    lines += ["", "---", ""]

    # 약세/위험 TOP 20
    lines += [
        "## 📉 약세/위험 TOP 20",
        "",
        "| 순위 | 종목코드 | 종목명 | 시장 | 업종 | 당일 | 5일 | 20일 | 거래량비 | 약세점수 | 시그널 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(bearish_top, 1):
        vr = f"{r['volume_ratio_5d']:.1f}x" if r.get("volume_ratio_5d") is not None else "-"
        lines.append(
            f"| {i} | {r['stock_code']} | {r.get('stock_name','-')} | {r.get('market','-')} | "
            f"{r.get('sector') or '-'} | {_fmt_pct(r.get('daily_return'))} | "
            f"{_fmt_pct(r.get('return_5d'))} | {_fmt_pct(r.get('return_20d'))} | "
            f"{vr} | {_fmt_f(r.get('bearish_score'))} | {r.get('final_signal','-')} |"
        )

    lines += ["", "---", ""]

    # 거래량 급증
    if high_volume:
        lines += [
            "## 📊 거래량 급증 종목",
            "",
            "| 종목코드 | 종목명 | 거래량비(5일) | 당일등락 | 강세점수 | 시그널 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in high_volume:
            vr = f"{r['volume_ratio_5d']:.1f}x" if r.get("volume_ratio_5d") is not None else "-"
            lines.append(
                f"| {r['stock_code']} | {r.get('stock_name','-')} | {vr} | "
                f"{_fmt_pct(r.get('daily_return'))} | {_fmt_f(r.get('bullish_score'))} | {r.get('final_signal','-')} |"
            )
        lines += ["", "---", ""]

    # 공시 이슈
    if disclosures:
        lines += [
            "## 📢 공시 이슈 종목",
            "",
            "| 종목코드 | 종목명 | 공시 제목 | 구분 | 위험도 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for d in disclosures:
            t = d["title"][:50] + "…" if len(d["title"]) > 50 else d["title"]
            lines.append(
                f"| {d['stock_code']} | {d['stock_name']} | {t} | {d['disclosure_type']} | {d['risk_level']} |"
            )
        lines += ["", "---", ""]

    # 관심 종목
    if watchlist:
        lines += ["## ⭐ 관심 종목 요약", ""]
        for group in watchlist:
            lines += [f"### {group['group_name']}", ""]
            if group.get("description"):
                lines += [f"*{group['description']}*", ""]
            lines += [
                "| 종목코드 | 종목명 | 시그널 | 당일 | 5일 | 강세점수 | 메모 |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
            for s in group["stocks"]:
                memo = (s.get("memo") or "")[:30]
                lines.append(
                    f"| {s['stock_code']} | {s['stock_name']} | {s['final_signal']} | "
                    f"{_fmt_pct(s.get('daily_return'))} | {_fmt_pct(s.get('return_5d'))} | "
                    f"{_fmt_f(s.get('bullish_score'))} | {memo} |"
                )
            lines += [""]
        lines += ["---", ""]

    # 위험 종목 요약
    if risk_stocks:
        lines += [
            "## ⚠️ 위험 종목 요약",
            "",
            "| 종목코드 | 종목명 | 시장 | 당일 | 5일 | 20일 | RSI | 약세점수 | 사유 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in risk_stocks[:20]:
            reason = (r.get("signal_reason") or "")[:60]
            lines.append(
                f"| {r['stock_code']} | {r.get('stock_name','-')} | {r.get('market','-')} | "
                f"{_fmt_pct(r.get('daily_return'))} | {_fmt_pct(r.get('return_5d'))} | "
                f"{_fmt_pct(r.get('return_20d'))} | {_fmt_f(r.get('rsi14'))} | "
                f"{_fmt_f(r.get('bearish_score'))} | {reason} |"
            )
        lines += ["", "---", ""]

    lines += [f"*생성 시각: {report_date} | {DISCLAIMER}*"]
    return "\n".join(lines)


# ── HTML 빌더 ────────────────────────────────────────────────────

_HTML_CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1300px;margin:0 auto;padding:24px;color:#222;background:#f5f6fa}
h1{color:#1a1a2e;border-bottom:3px solid #e94560;padding-bottom:10px;font-size:1.8rem}
h2{color:#16213e;border-left:5px solid #e94560;padding-left:12px;margin-top:36px;font-size:1.2rem}
h3{color:#0f3460;font-size:1rem;margin-top:20px}
.card{background:#fff;border-radius:8px;padding:16px;margin:12px 0;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.disclaimer{background:#fff8e1;border-left:4px solid #ffc107;padding:10px 16px;border-radius:4px;margin:12px 0;font-size:.9rem}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}
th{background:#1a1a2e;color:#fff;padding:9px 14px;text-align:left;white-space:nowrap}
td{padding:7px 14px;border-bottom:1px solid #eee}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#f8f9ff}
tr:hover td{background:#e8f4fd}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}
.bull{background:#e8f5e9;color:#2e7d32}.bear{background:#ffebee;color:#c62828}
.neutral{background:#e3f2fd;color:#1565c0}.watch{background:#fff8e1;color:#f57f17}
.risk{background:#fce4ec;color:#880e4f}
hr{border:none;border-top:1px solid #ddd;margin:24px 0}
.footer{color:#888;font-size:11px;margin-top:32px;padding-top:12px;border-top:1px solid #ddd;text-align:center}
.pct-pos{color:#c62828;font-weight:600}.pct-neg{color:#1565c0;font-weight:600}
""".strip()

_SIGNAL_BADGE = {
    "강세 관심": "bull", "추세 유지": "watch", "관망": "neutral",
    "약세 주의": "bear", "하락 위험": "risk",
}


def _pct_td(v) -> str:
    if v is None:
        return "<td>-</td>"
    f = float(v)
    cls = "pct-pos" if f > 0 else ("pct-neg" if f < 0 else "")
    return f'<td class="{cls}">{f:+.2f}%</td>'


def _signal_td(sig) -> str:
    cls = _SIGNAL_BADGE.get(sig or "", "neutral")
    return f'<td><span class="badge {cls}">{sig or "-"}</span></td>'


def _th(*cols) -> str:
    return "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"


def _build_html(
    report_date: date,
    title: str,
    indices: list[dict],
    summary: dict,
    sector_top: list[dict],
    sector_bottom: list[dict],
    bullish_top: list[dict],
    bearish_top: list[dict],
    high_volume: list[dict],
    disclosures: list[dict],
    watchlist: list[dict],
    risk_stocks: list[dict],
) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ko"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{title}</title>",
        f"<style>{_HTML_CSS}</style>",
        "</head><body>",
        f"<h1>📊 일일 시장 분석 리포트 — {report_date}</h1>",
        f'<div class="disclaimer">⚠️ {DISCLAIMER}</div>',
        "<h2>시장 요약</h2>",
        '<div class="card">',
    ]

    # 지수
    for idx in indices:
        cr = float(idx["change_rate"]) if idx.get("change_rate") is not None else None
        cr_str = f"{cr:+.2f}%" if cr is not None else "N/A"
        cls = "pct-pos" if (cr or 0) > 0 else ("pct-neg" if (cr or 0) < 0 else "")
        cv = f"{idx['close_value']:,.2f}" if idx.get("close_value") else "-"
        parts.append(f'<p><strong>{idx["name"]}</strong>: {cv} <span class="{cls}">({cr_str})</span></p>')

    total = summary.get("total", 0)
    bullish_cnt = summary.get("강세 관심", 0)
    bearish_cnt = summary.get("하락 위험", 0) + summary.get("약세 주의", 0)
    parts.append(
        f"<p><strong>분석 종목 수</strong>: {total}개 &nbsp;|&nbsp; "
        f'<strong class="pct-pos">강세 관심</strong>: {bullish_cnt}개 &nbsp;|&nbsp; '
        f'<strong class="pct-neg">약세/위험</strong>: {bearish_cnt}개</p>'
    )

    # 요약 테이블
    parts.append('<table><thead>' + _th("시그널", "종목 수") + "</thead><tbody>")
    for sig in _SIGNAL_ORDER:
        badge_cls = _SIGNAL_BADGE.get(sig, "neutral")
        parts.append(
            f'<tr><td><span class="badge {badge_cls}">{sig}</span></td>'
            f"<td>{summary.get(sig, 0)}개</td></tr>"
        )
    parts.append("</tbody></table></div>")

    # 강세 업종
    if sector_top:
        parts += [
            "<h2>📈 강세 업종 TOP 5</h2>",
            '<table><thead>' + _th("업종", "종목 수", "평균 당일", "평균 5일", "강세 점수") + "</thead><tbody>",
        ]
        for s in sector_top:
            parts.append(
                f"<tr><td>{s['sector']}</td><td>{s['count']}개</td>"
                + _pct_td(s["avg_daily_return"])
                + _pct_td(s["avg_return_5d"])
                + f"<td>{s['avg_bullish']:.1f}</td></tr>"
            )
        parts.append("</tbody></table>")

    # 약세 업종
    if sector_bottom:
        parts += [
            "<h2>📉 약세 업종 TOP 5</h2>",
            '<table><thead>' + _th("업종", "종목 수", "평균 당일", "평균 5일", "약세 점수") + "</thead><tbody>",
        ]
        for s in sector_bottom:
            parts.append(
                f"<tr><td>{s['sector']}</td><td>{s['count']}개</td>"
                + _pct_td(s["avg_daily_return"])
                + _pct_td(s["avg_return_5d"])
                + f"<td>{s['avg_bearish']:.1f}</td></tr>"
            )
        parts.append("</tbody></table>")

    # 강세 TOP 20
    parts += [
        "<h2>🔥 강세 관심 TOP 20</h2>",
        '<table><thead>' + _th("#", "코드", "종목명", "시장", "업종", "당일", "5일", "20일", "거래량비", "RSI", "강세점수", "시그널") + "</thead><tbody>",
    ]
    for i, r in enumerate(bullish_top, 1):
        vr = f"{float(r['volume_ratio_5d']):.1f}x" if r.get("volume_ratio_5d") is not None else "-"
        rsi = f"{float(r['rsi14']):.1f}" if r.get("rsi14") is not None else "-"
        bs = f"{float(r['bullish_score']):.1f}" if r.get("bullish_score") is not None else "-"
        parts.append(
            f"<tr><td>{i}</td><td>{r['stock_code']}</td><td>{r.get('stock_name','-')}</td>"
            f"<td>{r.get('market','-')}</td><td>{r.get('sector') or '-'}</td>"
            + _pct_td(r.get("daily_return")) + _pct_td(r.get("return_5d")) + _pct_td(r.get("return_20d"))
            + f"<td>{vr}</td><td>{rsi}</td><td>{bs}</td>"
            + _signal_td(r.get("final_signal")) + "</tr>"
        )
    parts.append("</tbody></table>")

    # 약세/위험 TOP 20
    parts += [
        "<h2>📉 약세/위험 TOP 20</h2>",
        '<table><thead>' + _th("#", "코드", "종목명", "시장", "업종", "당일", "5일", "20일", "거래량비", "약세점수", "시그널") + "</thead><tbody>",
    ]
    for i, r in enumerate(bearish_top, 1):
        vr = f"{float(r['volume_ratio_5d']):.1f}x" if r.get("volume_ratio_5d") is not None else "-"
        bs = f"{float(r['bearish_score']):.1f}" if r.get("bearish_score") is not None else "-"
        parts.append(
            f"<tr><td>{i}</td><td>{r['stock_code']}</td><td>{r.get('stock_name','-')}</td>"
            f"<td>{r.get('market','-')}</td><td>{r.get('sector') or '-'}</td>"
            + _pct_td(r.get("daily_return")) + _pct_td(r.get("return_5d")) + _pct_td(r.get("return_20d"))
            + f"<td>{vr}</td><td>{bs}</td>"
            + _signal_td(r.get("final_signal")) + "</tr>"
        )
    parts.append("</tbody></table>")

    # 거래량 급증
    if high_volume:
        parts += [
            "<h2>📊 거래량 급증 종목</h2>",
            '<table><thead>' + _th("코드", "종목명", "시장", "거래량비(5일)", "당일", "강세점수", "시그널") + "</thead><tbody>",
        ]
        for r in high_volume:
            vr = f"{float(r['volume_ratio_5d']):.1f}x" if r.get("volume_ratio_5d") is not None else "-"
            bs = f"{float(r['bullish_score']):.1f}" if r.get("bullish_score") is not None else "-"
            parts.append(
                f"<tr><td>{r['stock_code']}</td><td>{r.get('stock_name','-')}</td>"
                f"<td>{r.get('market','-')}</td><td><strong>{vr}</strong></td>"
                + _pct_td(r.get("daily_return"))
                + f"<td>{bs}</td>"
                + _signal_td(r.get("final_signal")) + "</tr>"
            )
        parts.append("</tbody></table>")

    # 공시 이슈
    if disclosures:
        parts += [
            "<h2>📢 공시 이슈 종목</h2>",
            '<table><thead>' + _th("코드", "종목명", "공시 제목", "구분", "위험도") + "</thead><tbody>",
        ]
        for d in disclosures:
            t = d["title"][:60] + "…" if len(d["title"]) > 60 else d["title"]
            url = d.get("url", "")
            title_cell = f'<a href="{url}" target="_blank">{t}</a>' if url else t
            parts.append(
                f"<tr><td>{d['stock_code']}</td><td>{d['stock_name']}</td>"
                f"<td>{title_cell}</td><td>{d['disclosure_type']}</td>"
                f"<td>{d['risk_level']}</td></tr>"
            )
        parts.append("</tbody></table>")

    # 관심 종목
    if watchlist:
        parts.append("<h2>⭐ 관심 종목 요약</h2>")
        for group in watchlist:
            parts.append(f"<h3>{group['group_name']}")
            if group.get("description"):
                parts.append(f" <small style='color:#888;font-weight:normal'>— {group['description']}</small>")
            parts.append("</h3>")
            parts += [
                '<table><thead>' + _th("코드", "종목명", "시장", "시그널", "당일", "5일", "강세점수", "메모") + "</thead><tbody>",
            ]
            for s in group["stocks"]:
                bs = f"{float(s['bullish_score']):.1f}" if s.get("bullish_score") is not None else "-"
                memo = (s.get("memo") or "")[:30]
                parts.append(
                    f"<tr><td>{s['stock_code']}</td><td>{s['stock_name']}</td>"
                    f"<td>{s.get('market','-')}</td>"
                    + _signal_td(s.get("final_signal"))
                    + _pct_td(s.get("daily_return")) + _pct_td(s.get("return_5d"))
                    + f"<td>{bs}</td><td>{memo}</td></tr>"
                )
            parts.append("</tbody></table>")

    # 위험 종목
    if risk_stocks:
        parts += [
            "<h2>⚠️ 위험 종목 요약</h2>",
            '<table><thead>' + _th("코드", "종목명", "시장", "당일", "5일", "20일", "RSI", "약세점수", "시그널") + "</thead><tbody>",
        ]
        for r in risk_stocks[:20]:
            rsi = f"{float(r['rsi14']):.1f}" if r.get("rsi14") is not None else "-"
            bs = f"{float(r['bearish_score']):.1f}" if r.get("bearish_score") is not None else "-"
            parts.append(
                f"<tr><td>{r['stock_code']}</td><td>{r.get('stock_name','-')}</td>"
                f"<td>{r.get('market','-')}</td>"
                + _pct_td(r.get("daily_return")) + _pct_td(r.get("return_5d")) + _pct_td(r.get("return_20d"))
                + f"<td>{rsi}</td><td>{bs}</td>"
                + _signal_td(r.get("final_signal")) + "</tr>"
            )
        parts.append("</tbody></table>")

    parts.append(f'<div class="footer">{report_date} 생성 | {DISCLAIMER}</div>')
    parts += ["</body></html>"]
    return "\n".join(parts)


# ── CSV 생성 ─────────────────────────────────────────────────────

def generate_csv_content(report_date: Optional[date] = None) -> str:
    """분석 결과 전체를 CSV 형식 문자열로 반환합니다."""
    target_date = report_date or date.today()
    session = get_db_session()
    try:
        q = (
            select(StockAnalysisResult, Stock.stock_name, Stock.market, Stock.sector)
            .join(Stock, StockAnalysisResult.stock_code == Stock.stock_code, isouter=True)
            .where(StockAnalysisResult.analysis_date == target_date)
            .order_by(StockAnalysisResult.bullish_score.desc())
        )
        rows = session.execute(q).all()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "종목코드", "종목명", "시장", "업종", "분석일",
            "당일수익률(%)", "5일수익률(%)", "20일수익률(%)", "60일수익률(%)",
            "거래량비(5일)", "거래량비(20일)",
            "MA5", "MA20", "MA60", "MA120",
            "RSI14", "변동성(20일)", "상대강도",
            "모멘텀점수", "거래량점수", "추세점수", "위험점수",
            "강세점수", "약세점수", "시그널", "시그널사유",
        ])
        for r in rows:
            ar = r.StockAnalysisResult
            writer.writerow([
                ar.stock_code, r.stock_name or "", r.market or "", r.sector or "",
                str(ar.analysis_date),
                _safe_float(ar.daily_return), _safe_float(ar.return_5d),
                _safe_float(ar.return_20d), _safe_float(ar.return_60d),
                _safe_float(ar.volume_ratio_5d), _safe_float(ar.volume_ratio_20d),
                _safe_float(ar.ma5), _safe_float(ar.ma20),
                _safe_float(ar.ma60), _safe_float(ar.ma120),
                _safe_float(ar.rsi14), _safe_float(ar.volatility_20d),
                _safe_float(ar.relative_strength),
                _safe_float(ar.momentum_score), _safe_float(ar.volume_score),
                _safe_float(ar.trend_score), _safe_float(ar.risk_score),
                _safe_float(ar.bullish_score), _safe_float(ar.bearish_score),
                ar.final_signal or "", ar.signal_reason or "",
            ])
        return buf.getvalue()
    finally:
        session.close()


def _safe_float(v) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.4f}"
    except (TypeError, ValueError):
        return ""


# ── 리포트 생성 (메인) ───────────────────────────────────────────

def generate_daily_report(report_date: Optional[date] = None) -> dict:
    """일일 시장 분석 리포트를 생성하고 DB 및 파일에 저장합니다."""
    target_date = report_date or date.today()
    session = get_db_session()

    try:
        # 데이터 수집
        summary = get_analysis_summary(target_date)
        bullish_top = get_analysis_results(target_date, order_by="bullish_score", limit=20)
        bearish_top = get_analysis_results(target_date, order_by="bearish_score", limit=20)
        high_volume = get_high_volume_stocks(target_date, min_ratio=2.0, limit=15)
        risk_stocks = get_analysis_results(target_date, signal="하락 위험", order_by="bearish_score", limit=20)

        indices = _get_market_indices(target_date, session)
        sector_top, sector_bottom = _get_sector_analysis(target_date, session)
        disclosures = _get_disclosure_stocks(target_date, session)
        watchlist = _get_watchlist_summary(target_date, session)

        total = summary.get("total", 0)
        bullish_cnt = summary.get("강세 관심", 0)
        bearish_cnt = summary.get("하락 위험", 0) + summary.get("약세 주의", 0)
        title = f"일일 시장 분석 리포트 - {target_date}"

        market_summary_str = "\n".join(
            f"- {idx['name']}: {idx['close_value']:,.2f} ({idx['change_rate']:+.2f}%)"
            for idx in indices
            if idx.get("close_value") and idx.get("change_rate") is not None
        ) or "시장 지수 데이터 없음"

        disclosure_summary_str = (
            f"{len(disclosures)}건" if disclosures else None
        )

        md = _build_markdown(
            target_date, indices, summary,
            sector_top, sector_bottom,
            bullish_top, bearish_top,
            high_volume, disclosures, watchlist, risk_stocks,
        )

        html = _build_html(
            target_date, title, indices, summary,
            sector_top, sector_bottom,
            bullish_top, bearish_top,
            high_volume, disclosures, watchlist, risk_stocks,
        )

        json_content = {
            "report_date": str(target_date),
            "summary": summary,
            "indices": indices,
            "sector_top": sector_top,
            "sector_bottom": sector_bottom,
            "bullish_top20": bullish_top,
            "bearish_top20": bearish_top,
            "high_volume": high_volume,
            "disclosures": disclosures,
            "watchlist": watchlist,
            "risk_stocks": risk_stocks,
        }

        # DB upsert: report_date 기준으로 기존 행 확인 후 UPDATE, 없으면 INSERT
        existing = session.execute(
            select(DailyMarketReport)
            .where(DailyMarketReport.report_date == target_date)
            .order_by(DailyMarketReport.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        if existing:
            existing.title = title
            existing.market_summary = market_summary_str
            existing.bullish_summary = f"강세 관심 {bullish_cnt}개"
            existing.bearish_summary = f"약세/위험 {bearish_cnt}개"
            existing.disclosure_summary = disclosure_summary_str
            existing.markdown_content = md
            existing.html_content = html
            existing.json_content = json_content
            session.commit()
        else:
            row = DailyMarketReport(
                report_date=target_date,
                title=title,
                market_summary=market_summary_str,
                bullish_summary=f"강세 관심 {bullish_cnt}개",
                bearish_summary=f"약세/위험 {bearish_cnt}개",
                disclosure_summary=disclosure_summary_str,
                markdown_content=md,
                html_content=html,
                json_content=json_content,
            )
            session.add(row)
            session.commit()

        # 파일 저장
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        (reports_dir / f"report_{target_date}.md").write_text(md, encoding="utf-8")
        (reports_dir / f"report_{target_date}.html").write_text(html, encoding="utf-8")
        logger.info(f"리포트 생성 완료: {target_date}")

        return {
            "status": "success",
            "date": str(target_date),
            "file_md": f"reports/report_{target_date}.md",
            "file_html": f"reports/report_{target_date}.html",
            "bullish_count": bullish_cnt,
            "bearish_count": bearish_cnt,
            "total_analyzed": total,
            "sector_top": [s["sector"] for s in sector_top],
            "sector_bottom": [s["sector"] for s in sector_bottom],
            "disclosures": len(disclosures),
            "watchlist_groups": len(watchlist),
        }

    except Exception as e:
        logger.error(f"generate_daily_report 실패: {e}", exc_info=True)
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


# ── 조회 함수 ────────────────────────────────────────────────────

def get_latest_report() -> Optional[dict]:
    """가장 최근 리포트를 반환합니다."""
    session = get_db_session()
    try:
        q = select(DailyMarketReport).order_by(DailyMarketReport.report_date.desc()).limit(1)
        row = session.execute(q).scalar_one_or_none()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        session.close()


def get_report_by_date(report_date: date) -> Optional[dict]:
    """특정 날짜의 리포트를 반환합니다."""
    session = get_db_session()
    try:
        q = (
            select(DailyMarketReport)
            .where(DailyMarketReport.report_date == report_date)
            .order_by(DailyMarketReport.id.desc())
            .limit(1)
        )
        row = session.execute(q).scalar_one_or_none()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        session.close()


def get_reports_list() -> list[dict]:
    """저장된 리포트 목록을 반환합니다."""
    session = get_db_session()
    try:
        q = (
            select(
                DailyMarketReport.report_date,
                DailyMarketReport.title,
                DailyMarketReport.bullish_summary,
                DailyMarketReport.bearish_summary,
                DailyMarketReport.market_summary,
                DailyMarketReport.created_at,
            )
            .order_by(DailyMarketReport.report_date.desc())
            .distinct(DailyMarketReport.report_date)
        )
        rows = session.execute(q).all()
        return [
            {
                "report_date": str(r.report_date),
                "title": r.title,
                "bullish_summary": r.bullish_summary,
                "bearish_summary": r.bearish_summary,
                "market_summary": r.market_summary,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ]
    finally:
        session.close()


def _row_to_dict(row: DailyMarketReport) -> dict:
    return {
        "report_date": str(row.report_date),
        "title": row.title,
        "market_summary": row.market_summary,
        "bullish_summary": row.bullish_summary,
        "bearish_summary": row.bearish_summary,
        "disclosure_summary": row.disclosure_summary,
        "markdown_content": row.markdown_content,
        "html_content": row.html_content,
        "json_content": row.json_content,
    }
