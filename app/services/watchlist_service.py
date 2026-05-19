"""
관심종목 자동 선정 서비스
stock_analysis_results 분석 결과 기준으로 단기/장기 관심종목을 watchlist에 upsert합니다.
"""
import logging
from datetime import date
from typing import Optional

from sqlalchemy import and_, or_, select

from app.database import get_db_session
from app.models.analysis import StockAnalysisResult
from app.models.watchlist import WatchlistGroup, WatchlistItem

logger = logging.getLogger(__name__)

GROUP_SHORT = "단기 관심종목 (자동)"
GROUP_LONG  = "장기 관심종목 (자동)"

# 선정 임계값
SHORT_MOMENTUM_MIN = 12
SHORT_VOLUME_MIN   = 8
SHORT_RISK_MAX     = 20
SHORT_LIMIT        = 20

LONG_TREND_MIN     = 12
LONG_RS_MIN        = 0.0
LONG_RISK_MAX      = 20
LONG_LIMIT         = 20


def _build_memo(row: StockAnalysisResult, is_short: bool = True) -> str:
    """
    그룹 유형에 맞는 선정 사유 메모 생성 (500자 제한, 참고용).
    단기/장기 각각 선정 기준으로 쓰인 지표를 명시합니다.
    """
    def _f(v): return float(v) if v is not None else None

    r5    = _f(row.return_5d)
    r20   = _f(row.return_20d)
    r60   = _f(row.return_60d)
    mom   = _f(row.momentum_score)
    vols  = _f(row.volume_score)
    trd   = _f(row.trend_score)
    risk  = _f(row.risk_score)
    rs    = _f(row.relative_strength)
    vol5  = _f(row.volume_ratio_5d)
    ma20  = _f(row.ma20)
    ma60  = _f(row.ma60)
    ma120 = _f(row.ma120)

    parts = []

    if is_short:
        # ── 단기 선정 기준 명시 ──────────────────────────────
        parts.append(f"[단기 모멘텀 선정]")
        parts.append(f"시그널: {row.final_signal or '-'}")

        if r5 is not None:
            parts.append(f"5일수익률 {r5:+.1f}%")
        if r20 is not None:
            parts.append(f"20일수익률 {r20:+.1f}%")
        if vol5 is not None:
            lbl = f"거래량비율 {vol5:.1f}배({'평균 대비 급증' if vol5 >= 2 else '평균 대비 증가' if vol5 >= 1.3 else '평이'})"
            parts.append(lbl)
        if mom is not None:
            parts.append(f"모멘텀점수 {mom:.0f}점")
        if vols is not None:
            parts.append(f"거래량점수 {vols:.0f}점")
        if risk is not None:
            parts.append(f"위험점수 {risk:.0f}점({'과도하지 않음' if risk <= SHORT_RISK_MAX else '주의 필요'})")

    else:
        # ── 장기 선정 기준 명시 ──────────────────────────────
        parts.append(f"[중기 추세 선정]")
        parts.append(f"시그널: {row.final_signal or '-'}")

        # MA 배열 상태
        if ma20 and ma60:
            if ma20 >= ma60:
                parts.append(f"MA20({ma20:,.0f}원)≥MA60({ma60:,.0f}원) 상승정배열")
            else:
                parts.append(f"MA20({ma20:,.0f}원)<MA60({ma60:,.0f}원)")
        if ma60 and ma120:
            if ma60 >= ma120:
                parts.append(f"MA60≥MA120 장기정배열")
            else:
                parts.append(f"MA60<MA120")

        if r20 is not None:
            parts.append(f"20일수익률 {r20:+.1f}%")
        if r60 is not None:
            parts.append(f"60일수익률 {r60:+.1f}%")
        if rs is not None:
            lbl = f"상대강도 {rs:+.1f}%p({'시장 대비 강세' if rs > 0 else '시장 대비 약세'})"
            parts.append(lbl)
        if trd is not None:
            parts.append(f"추세점수 {trd:.0f}점")
        if risk is not None:
            parts.append(f"위험점수 {risk:.0f}점({'과도하지 않음' if risk <= LONG_RISK_MAX else '주의 필요'})")

    # signal_reason이 있으면 참고로 덧붙임
    base = " | ".join(parts)
    if row.signal_reason:
        combined = f"{base} || 분석사유: {row.signal_reason}"
        return combined[:500]

    return base[:500] if base else "자동 선정 종목 (참고용)"


def _upsert_group(session, group_name: str, description: str) -> int:
    """watchlist_groups upsert. group_id 반환."""
    grp = session.execute(
        select(WatchlistGroup).where(WatchlistGroup.group_name == group_name)
    ).scalar_one_or_none()

    if grp is None:
        grp = WatchlistGroup(group_name=group_name, description=description)
        session.add(grp)
        session.flush()
        logger.info(f"[자동선정] 그룹 생성: {group_name} (id={grp.id})")
    else:
        grp.description = description
        logger.info(f"[자동선정] 그룹 업데이트: {group_name} (id={grp.id})")

    return grp.id


def _upsert_item(session, group_id: int, stock_code: str, memo: str) -> bool:
    """watchlist_items upsert. True=신규 삽입, False=메모 업데이트."""
    item = session.execute(
        select(WatchlistItem).where(
            and_(
                WatchlistItem.group_id == group_id,
                WatchlistItem.stock_code == stock_code,
            )
        )
    ).scalar_one_or_none()

    if item is None:
        session.add(WatchlistItem(group_id=group_id, stock_code=stock_code, memo=memo))
        return True

    item.memo = memo
    return False


def auto_select_watchlist(analysis_date: Optional[date] = None) -> dict:
    """
    분석 결과 기준으로 단기/장기 관심종목을 자동 선정하여 watchlist에 upsert합니다.

    단기 기준: final_signal='강세 관심', momentum_score/volume_score 양호, risk_score 과도 아님
    장기 기준: final_signal IN('강세 관심','추세 유지'), MA 정배열 일부, trend_score/relative_strength 양호
    """
    target_date = analysis_date or date.today()
    session = get_db_session()

    try:
        # ── 단기 관심종목 ─────────────────────────────────────
        short_rows = session.execute(
            select(StockAnalysisResult)
            .where(
                and_(
                    StockAnalysisResult.analysis_date == target_date,
                    StockAnalysisResult.final_signal == "강세 관심",
                    StockAnalysisResult.momentum_score >= SHORT_MOMENTUM_MIN,
                    StockAnalysisResult.volume_score   >= SHORT_VOLUME_MIN,
                    StockAnalysisResult.risk_score     <= SHORT_RISK_MAX,
                )
            )
            .order_by(
                StockAnalysisResult.momentum_score.desc(),
                StockAnalysisResult.volume_score.desc(),
            )
            .limit(SHORT_LIMIT)
        ).scalars().all()

        # ── 장기 관심종목 ─────────────────────────────────────
        long_rows = session.execute(
            select(StockAnalysisResult)
            .where(
                and_(
                    StockAnalysisResult.analysis_date == target_date,
                    StockAnalysisResult.final_signal.in_(["강세 관심", "추세 유지"]),
                    StockAnalysisResult.trend_score       >= LONG_TREND_MIN,
                    StockAnalysisResult.relative_strength >= LONG_RS_MIN,
                    StockAnalysisResult.risk_score        <= LONG_RISK_MAX,
                    or_(
                        and_(
                            StockAnalysisResult.ma20 != None,
                            StockAnalysisResult.ma60 != None,
                            StockAnalysisResult.ma20 >= StockAnalysisResult.ma60,
                        ),
                        and_(
                            StockAnalysisResult.ma60 != None,
                            StockAnalysisResult.ma120 != None,
                            StockAnalysisResult.ma60 >= StockAnalysisResult.ma120,
                        ),
                    ),
                )
            )
            .order_by(
                StockAnalysisResult.trend_score.desc(),
                StockAnalysisResult.relative_strength.desc(),
            )
            .limit(LONG_LIMIT)
        ).scalars().all()

        # ── 그룹 upsert ───────────────────────────────────────
        short_gid = _upsert_group(
            session,
            GROUP_SHORT,
            f"자동 선정 단기 관심종목 — {target_date} 기준 (참고용)",
        )
        long_gid = _upsert_group(
            session,
            GROUP_LONG,
            f"자동 선정 장기 관심종목 — {target_date} 기준 (참고용)",
        )

        # ── 종목 upsert ───────────────────────────────────────
        short_ins = short_upd = 0
        for row in short_rows:
            if _upsert_item(session, short_gid, row.stock_code, _build_memo(row, is_short=True)):
                short_ins += 1
            else:
                short_upd += 1

        long_ins = long_upd = 0
        for row in long_rows:
            if _upsert_item(session, long_gid, row.stock_code, _build_memo(row, is_short=False)):
                long_ins += 1
            else:
                long_upd += 1

        session.commit()

        result = {
            "status":  "success",
            "date":    str(target_date),
            "short_term": {
                "group": GROUP_SHORT,
                "group_id": short_gid,
                "selected": len(short_rows),
                "inserted": short_ins,
                "updated":  short_upd,
            },
            "long_term": {
                "group": GROUP_LONG,
                "group_id": long_gid,
                "selected": len(long_rows),
                "inserted": long_ins,
                "updated":  long_upd,
            },
        }
        logger.info(
            f"[자동선정] 완료 — 단기 {len(short_rows)}개, 장기 {len(long_rows)}개"
        )
        return result

    except Exception as e:
        session.rollback()
        logger.error(f"[자동선정] 실패: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

    finally:
        session.close()
