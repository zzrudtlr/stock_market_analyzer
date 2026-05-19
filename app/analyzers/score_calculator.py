"""
강세/약세 점수 계산기
- 모든 점수는 0~100 범위
- 예측이 아닌 추세/모멘텀/리스크 기반 점수
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        v = float(val)
        return v if np.isfinite(v) else None
    except Exception:
        return None


def calculate_metrics(prices_df: pd.DataFrame) -> Optional[dict]:
    """
    가격 데이터 DataFrame으로 기술적 지표를 계산합니다.

    prices_df: trade_date 오름차순 정렬된 DataFrame
               필수 컬럼: close_price, volume
    반환값: 지표 dict 또는 데이터 부족 시 None
    """
    if prices_df is None or len(prices_df) < 2:
        return None

    close = prices_df["close_price"].astype(float)
    volume = prices_df["volume"].fillna(0).astype(float)
    n = len(close)

    # --- 수익률 ---
    daily_return = _safe_float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if n >= 2 else None
    return_5d = _safe_float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if n >= 6 else None
    return_20d = _safe_float((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21] * 100) if n >= 21 else None
    return_60d = _safe_float((close.iloc[-1] - close.iloc[-61]) / close.iloc[-61] * 100) if n >= 61 else None

    # --- 이동평균 ---
    ma5 = _safe_float(close.iloc[-5:].mean()) if n >= 5 else None
    ma20 = _safe_float(close.iloc[-20:].mean()) if n >= 20 else None
    ma60 = _safe_float(close.iloc[-60:].mean()) if n >= 60 else None
    ma120 = _safe_float(close.iloc[-120:].mean()) if n >= 120 else None

    # --- 거래량 비율 (오늘 거래량 vs 직전 N일 평균, 오늘 제외) ---
    vol_today = float(volume.iloc[-1]) if n >= 1 else 0
    avg_vol_5 = float(volume.iloc[-6:-1].mean()) if n >= 6 else 0
    avg_vol_20 = float(volume.iloc[-21:-1].mean()) if n >= 21 else 0
    volume_ratio_5d = _safe_float(vol_today / avg_vol_5) if avg_vol_5 > 0 else None
    volume_ratio_20d = _safe_float(vol_today / avg_vol_20) if avg_vol_20 > 0 else None

    # --- RSI 14 ---
    rsi14 = None
    if n >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = 100 - (100 / (1 + rs))
        rsi14 = _safe_float(rsi_series.iloc[-1])

    # --- 20일 변동성 ---
    volatility_20d = None
    if n >= 20:
        daily_rets = close.pct_change()
        vol_val = daily_rets.iloc[-20:].std() * 100
        volatility_20d = _safe_float(vol_val)

    return {
        "daily_return": daily_return,
        "return_5d": return_5d,
        "return_20d": return_20d,
        "return_60d": return_60d,
        "volume_ratio_5d": volume_ratio_5d,
        "volume_ratio_20d": volume_ratio_20d,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "rsi14": rsi14,
        "volatility_20d": volatility_20d,
        "close_now": float(close.iloc[-1]),
    }


def calculate_scores(metrics: dict, market_return_20d: Optional[float] = None) -> dict:
    """
    기술적 지표를 바탕으로 강세/약세 점수를 계산합니다.
    모든 점수는 0~100 범위.
    """
    dr = metrics.get("daily_return") or 0.0
    r5 = metrics.get("return_5d") or 0.0
    r20 = metrics.get("return_20d") or 0.0
    vr5 = metrics.get("volume_ratio_5d") or 1.0
    rsi = metrics.get("rsi14")
    vol20 = metrics.get("volatility_20d") or 0.0
    close_now = metrics.get("close_now") or 0.0
    ma5 = metrics.get("ma5")
    ma20 = metrics.get("ma20")
    ma60 = metrics.get("ma60")

    # --- 상대 강도 ---
    relative_strength = 1.0
    if market_return_20d is not None and market_return_20d != 0:
        stock_factor = 1 + r20 / 100
        market_factor = 1 + market_return_20d / 100
        relative_strength = stock_factor / market_factor if market_factor != 0 else 1.0

    # === 강세 점수 구성 ===

    # 모멘텀 점수 (0~30)
    momentum = 0.0
    if dr > 3:
        momentum += 10
    elif dr > 1:
        momentum += 6
    elif dr > 0:
        momentum += 3

    if r5 > 7:
        momentum += 10
    elif r5 > 3:
        momentum += 6
    elif r5 > 0:
        momentum += 3

    if r20 > 15:
        momentum += 10
    elif r20 > 5:
        momentum += 6
    elif r20 > 0:
        momentum += 3

    # 거래량 점수 (0~20)
    vol_score = 0.0
    if vr5 > 3:
        vol_score = 20
    elif vr5 > 2:
        vol_score = 14
    elif vr5 > 1.5:
        vol_score = 9
    elif vr5 > 1.1:
        vol_score = 4

    # 추세 점수 (0~30)
    trend_score = 0.0
    if ma5 and close_now > ma5:
        trend_score += 10
    if ma20 and close_now > ma20:
        trend_score += 10
    if ma5 and ma20 and ma5 > ma20:
        trend_score += 10

    # 상대강도 보너스 (0~20)
    rs_score = 0.0
    if relative_strength > 1.1:
        rs_score = 20
    elif relative_strength > 1.05:
        rs_score = 12
    elif relative_strength > 1.0:
        rs_score = 6

    bullish_score = min(100.0, momentum + vol_score + trend_score + rs_score)

    # === 약세 점수 구성 ===

    # 음의 모멘텀 (0~30)
    neg_momentum = 0.0
    if dr < -3:
        neg_momentum += 10
    elif dr < -1:
        neg_momentum += 6
    elif dr < 0:
        neg_momentum += 3

    if r5 < -7:
        neg_momentum += 10
    elif r5 < -3:
        neg_momentum += 6
    elif r5 < 0:
        neg_momentum += 3

    if r20 < -15:
        neg_momentum += 10
    elif r20 < -5:
        neg_momentum += 6
    elif r20 < 0:
        neg_momentum += 3

    # 이탈 점수 (0~30)
    breakdown = 0.0
    if ma5 and close_now < ma5:
        breakdown += 10
    if ma20 and close_now < ma20:
        breakdown += 10
    if ma5 and ma20 and ma5 < ma20:
        breakdown += 10

    # 거래량 동반 하락 점수 (0~20)
    drop_vol = 0.0
    if dr < 0 and vr5 > 2:
        drop_vol = 20
    elif dr < 0 and vr5 > 1.5:
        drop_vol = 12
    elif dr < 0 and vr5 > 1.2:
        drop_vol = 6

    # 변동성 리스크 (0~20)
    risk_score = 0.0
    if vol20 > 10:
        risk_score = 20
    elif vol20 > 5:
        risk_score = 12
    elif vol20 > 3:
        risk_score = 6

    # RSI 과열/과매도 보정
    bearish_score_adj = 0.0
    if rsi is not None:
        if rsi > 75:
            bullish_score = max(0, bullish_score - 10)
            risk_score = min(20, risk_score + 5)
        elif rsi < 25:
            bearish_score_adj = 5.0

    bearish_score = min(100.0, neg_momentum + breakdown + drop_vol + risk_score + bearish_score_adj)

    return {
        "relative_strength": round(relative_strength, 4),
        "momentum_score": round(momentum, 4),
        "volume_score": round(vol_score, 4),
        "trend_score": round(trend_score, 4),
        "risk_score": round(risk_score, 4),
        "disclosure_score": 0.0,
        "bullish_score": round(bullish_score, 4),
        "bearish_score": round(bearish_score, 4),
    }


def determine_signal(
    bullish: float,
    bearish: float,
    metrics: Optional[dict] = None,
    scores: Optional[dict] = None,
) -> tuple[str, str]:
    """최종 시그널과 사유를 반환합니다."""
    if bullish >= 70:
        signal = "강세 관심"
    elif bullish >= 50 and bearish < 40:
        signal = "추세 유지"
    elif bearish >= 70:
        signal = "하락 위험"
    elif bearish >= 50:
        signal = "약세 주의"
    else:
        signal = "관망"

    parts = [f"강세 {bullish:.0f} / 약세 {bearish:.0f}"]

    if metrics:
        rsi = metrics.get("rsi14")
        r5 = metrics.get("return_5d")
        r20 = metrics.get("return_20d")
        vol20 = metrics.get("volatility_20d")
        close = metrics.get("close_now")
        ma5 = metrics.get("ma5")
        ma20_val = metrics.get("ma20")

        if rsi is not None:
            rsi_label = "과매수" if rsi > 70 else ("과매도" if rsi < 30 else "중립")
            parts.append(f"RSI {rsi:.1f}({rsi_label})")

        if r5 is not None:
            parts.append(f"5일수익률 {r5:+.1f}%")

        if r20 is not None:
            parts.append(f"20일수익률 {r20:+.1f}%")

        if close and ma5 and ma20_val:
            parts.append("MA 정배열" if ma5 > ma20_val else "MA 역배열")

        if vol20 is not None and vol20 > 5:
            parts.append(f"고변동성 {vol20:.1f}%")

    if scores:
        momentum = scores.get("momentum_score", 0)
        trend = scores.get("trend_score", 0)
        vol_sc = scores.get("volume_score", 0)
        parts.append(f"모멘텀 {momentum:.0f} / 추세 {trend:.0f} / 거래량 {vol_sc:.0f}")

    return signal, " | ".join(parts)
