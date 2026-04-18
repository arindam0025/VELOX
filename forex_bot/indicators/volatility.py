"""
Volatility: ATR, rolling percentile regimes, Bollinger bandwidth proxy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.indicators._common import atr, bollinger_bands, percentile_rank_last


def atr_dual(
    df: pd.DataFrame,
    short: int | None = None,
    long: int | None = None,
) -> pd.DataFrame:
    """
    Add ``atr_short`` and ``atr_long`` columns from configured periods.

    Args:
        df: OHLCV.
        short: Short ATR period.
        long: Long ATR period.

    Returns:
        DataFrame with ATR columns.
    """

    cfg = CONFIG.indicator_params
    s = short if short is not None else cfg.atr_period_short
    l_ = long if long is not None else cfg.atr_period_long
    return pd.DataFrame(
        {
            "atr_short": atr(df["high"], df["low"], df["close"], s),
            "atr_long": atr(df["high"], df["low"], df["close"], l_),
        },
        index=df.index,
    )


def volatility_regime(
    atr_series: pd.Series,
    *,
    window: int | None = None,
) -> pd.Series:
    """
    Classify volatility as ``low`` / ``medium`` / ``high`` via rolling ATR percentile.

    Args:
        atr_series: ATR series.
        window: Rolling window for percentile thresholds from config.

    Returns:
        Categorical string series.
    """

    cfg = CONFIG.indicator_params
    thr = CONFIG.thresholds
    w = window if window is not None else cfg.atr_regime_window
    pr = percentile_rank_last(atr_series, w)
    out = pd.Series("medium", index=atr_series.index, dtype=object)
    out = out.mask(pr < thr.atr_percentile_low / 100.0, "low")
    out = out.mask(pr > thr.atr_percentile_high / 100.0, "high")
    return out


def bollinger_bandwidth(
    close: pd.Series,
    period: int | None = None,
) -> pd.Series:
    """
    Bollinger Band width divided by middle band (percentage volatility proxy).

    Args:
        close: Close prices.
        period: BB period.

    Returns:
        Bandwidth series.
    """

    cfg = CONFIG.indicator_params
    p = period if period is not None else cfg.bb_period
    mid, upper, lower = bollinger_bands(close, p, cfg.bb_std)
    return (upper - lower) / mid.replace(0.0, np.nan)
