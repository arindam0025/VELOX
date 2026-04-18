"""
Price action: pivots, dynamic S/R, trendlines, and candlestick patterns.

Parameters are driven by ``CONFIG.indicator_params`` unless overridden.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG, AppConfig, IndicatorParamsConfig


def pivot_high_low(
    high: pd.Series,
    low: pd.Series,
    left_right: int | None = None,
) -> tuple[pd.Series, pd.Series]:
    """
    Fractal pivot highs and lows (center bar is strictly highest/lowest).

    Args:
        high: High prices.
        low: Low prices.
        left_right: Bars on each side (defaults to ``CONFIG.indicator_params``).

    Returns:
        Tuple of Series with NaN except at pivot locations (pivot value).
    """

    cfg = CONFIG.indicator_params
    lr = left_right if left_right is not None else cfg.pivot_left_right
    roll_max = high.rolling(window=2 * lr + 1, center=True, min_periods=2 * lr + 1).max()
    roll_min = low.rolling(window=2 * lr + 1, center=True, min_periods=2 * lr + 1).min()
    ph = high.where(high == roll_max)
    pl = low.where(low == roll_min)
    return ph, pl


def support_resistance_levels(
    df: pd.DataFrame,
    *,
    left_right: int | None = None,
    touch_merge_atr_ratio: float | None = None,
    config: AppConfig | None = None,
) -> pd.DataFrame:
    """
    Aggregate pivot levels into S/R with touch counts weighted by recency.

    Proximity merge uses ATR-based tolerance from config.

    Args:
        df: OHLCV with columns ``open, high, low, close`` and optional ``atr``.
        left_right: Pivot window half-width.
        touch_merge_atr_ratio: Merge levels within ``atr * ratio``.
        config: Optional ``AppConfig``.

    Returns:
        DataFrame with columns ``level``, ``kind`` (support/resistance), ``touches``.
    """

    cfg = (config or CONFIG).indicator_params
    lr = left_right if left_right is not None else cfg.pivot_left_right
    tol_ratio = (
        touch_merge_atr_ratio
        if touch_merge_atr_ratio is not None
        else cfg.liquidity_equal_tolerance_atr_ratio
    )

    ph, pl = pivot_high_low(df["high"], df["low"], lr)
    atr_col = df["atr"] if "atr" in df.columns else None
    if atr_col is None:
        from forex_bot.indicators._common import atr as atr_fn

        atr_col = atr_fn(df["high"], df["low"], df["close"], cfg.atr_period_short)

    levels: list[tuple[float, str, int]] = []
    for series, kind in [
        (ph.dropna(), "resistance"),
        (pl.dropna(), "support"),
    ]:
        for val in series.values:
            levels.append((float(val), kind, 1))

    if not levels:
        return pd.DataFrame(columns=["level", "kind", "touches"])

    levels.sort(key=lambda x: x[0])
    merged: list[list[float | str | int]] = []
    i = 0
    last_atr = float(atr_col.iloc[-1])
    tol = max(last_atr * tol_ratio, 1e-8)
    while i < len(levels):
        bucket_price = levels[i][0]
        bucket_kind = levels[i][1]
        touches = levels[i][2]
        j = i + 1
        while j < len(levels) and abs(levels[j][0] - bucket_price) <= tol:
            touches += levels[j][2]
            bucket_price = (bucket_price + levels[j][0]) / 2.0
            j += 1
        merged.append([bucket_price, bucket_kind, touches])
        i = j
    out = pd.DataFrame(merged, columns=["level", "kind", "touches"])
    return out


def linear_regression_trendline(
    swing_points: pd.Series,
    window: int | None = None,
) -> tuple[float, float]:
    """
    Fit ``close = slope * i + intercept`` on the last non-NaN swing points.

    Args:
        swing_points: Series indexed by time with NaNs except swing values.
        window: Maximum number of recent swings to use.

    Returns:
        Tuple ``(slope, intercept)`` in price-per-bar units.
    """

    cfg = CONFIG.indicator_params
    w = window if window is not None else cfg.trendline_regression_window
    vals = swing_points.dropna().tail(w)
    if len(vals) < cfg.trendline_min_swings:
        return float("nan"), float("nan")
    y = vals.to_numpy(dtype=float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _body_upper_lower(o: float, h: float, l: float, c: float) -> tuple[float, float, float]:
    """Return body top, body bottom, body size for a candle."""

    body_top = max(o, c)
    body_bot = min(o, c)
    body = abs(c - o)
    return body_top, body_bot, body


def detect_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized candlestick pattern flags (engulfing, pin bar, doji, etc.).

    Args:
        df: OHLCV with ``open, high, low, close``.

    Returns:
        Copy of ``df`` with boolean pattern columns appended.
    """

    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    n = len(df)
    out = df.copy()

    prev_o = np.roll(o, 1)
    prev_h = np.roll(h, 1)
    prev_l = np.roll(l, 1)
    prev_c = np.roll(c, 1)

    rng = h - l
    body = np.abs(c - o)
    prev_body = np.abs(prev_c - prev_o)
    upper_wick = h - np.maximum(o, c)
    lower_wick = np.minimum(o, c) - l

    bull_eng = (c > o) & (prev_c < prev_o) & (o <= prev_c) & (c >= prev_o) & (body > 0)
    bear_eng = (c < o) & (prev_c > prev_o) & (o >= prev_c) & (c <= prev_o) & (body > 0)

    pin_bar = (rng > 0) & (np.maximum(upper_wick, lower_wick) > 2.0 * body)
    doji = (rng > 0) & (body <= 0.1 * rng)

    inside = (h <= prev_h) & (l >= prev_l)

    hammer = (
        (rng > 0)
        & (lower_wick >= 2.0 * body)
        & (upper_wick <= 0.25 * rng)
        & (c > o)
    )
    shooting_star = (
        (rng > 0)
        & (upper_wick >= 2.0 * body)
        & (lower_wick <= 0.25 * rng)
        & (c < o)
    )

    morning_star = np.zeros(n, dtype=bool)
    evening_star = np.zeros(n, dtype=bool)
    for i in range(2, n):
        if (
            prev_c[i - 1] < prev_o[i - 1]
            and c[i - 2] < o[i - 2]
            and body[i - 1] < 0.3 * (prev_h[i - 1] - prev_l[i - 1])
            and c[i] > o[i]
            and c[i] > (o[i - 2] + c[i - 2]) / 2.0
        ):
            morning_star[i] = True
        if (
            prev_c[i - 1] > prev_o[i - 1]
            and c[i - 2] > o[i - 2]
            and body[i - 1] < 0.3 * (prev_h[i - 1] - prev_l[i - 1])
            and c[i] < o[i]
            and c[i] < (o[i - 2] + c[i - 2]) / 2.0
        ):
            evening_star[i] = True

    out["pattern_bull_engulfing"] = bull_eng
    out["pattern_bear_engulfing"] = bear_eng
    out["pattern_pin_bar"] = pin_bar
    out["pattern_doji"] = doji
    out["pattern_inside_bar"] = inside
    out["pattern_hammer"] = hammer
    out["pattern_shooting_star"] = shooting_star
    out["pattern_morning_star"] = morning_star
    out["pattern_evening_star"] = evening_star
    pattern_cols = [c for c in out.columns if c.startswith("pattern_")]
    out.loc[out.index[0], pattern_cols] = False
    out.loc[out.index[:2], ["pattern_morning_star", "pattern_evening_star"]] = False
    return out
