"""
Trend tools: EMA/SMA stacks, ADX, swing structure, pullback zones.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.indicators._common import atr, ema, sma, true_range


def add_emas(
    close: pd.Series,
    periods: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """
    Add EMA columns for configured periods.

    Args:
        close: Close prices.
        periods: EMA spans (defaults to ``CONFIG.indicator_params.ema_periods``).

    Returns:
        DataFrame with one column per period named ``ema_{period}``.
    """

    p = periods if periods is not None else CONFIG.indicator_params.ema_periods
    out = pd.DataFrame(index=close.index)
    for span in p:
        out[f"ema_{span}"] = ema(close, span)
    return out


def add_smas(
    close: pd.Series,
    periods: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """
    Add SMA columns for configured periods.

    Args:
        close: Close prices.
        periods: SMA windows.

    Returns:
        DataFrame with ``sma_{period}`` columns.
    """

    p = periods if periods is not None else CONFIG.indicator_params.sma_periods
    out = pd.DataFrame(index=close.index)
    for w in p:
        out[f"sma_{w}"] = sma(close, w)
    return out


def average_directional_index(
    df: pd.DataFrame,
    period: int | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Compute ADX, +DI, -DI (Wilder smoothing).

    Args:
        df: OHLCV.
        period: ADX period.

    Returns:
        Tuple ``(adx, plus_di, minus_di)``.
    """

    p = period if period is not None else CONFIG.indicator_params.adx_period
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = true_range(high, low, close)
    atr_s = tr.ewm(alpha=1.0 / p, adjust=False, min_periods=p).mean()
    plus_di = 100.0 * (
        plus_dm.ewm(alpha=1.0 / p, adjust=False, min_periods=p).mean() / atr_s
    )
    minus_di = 100.0 * (
        minus_dm.ewm(alpha=1.0 / p, adjust=False, min_periods=p).mean() / atr_s
    )
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan) * 100.0
    adx = dx.ewm(alpha=1.0 / p, adjust=False, min_periods=p).mean()
    return adx, plus_di, minus_di


def market_structure_labels(
    df: pd.DataFrame,
    lookback: int | None = None,
) -> pd.Series:
    """
    Label swing structure as ``HH``, ``HL``, ``LH``, ``LL`` vs prior swing.

    Args:
        df: OHLCV.
        lookback: Swing detection window.

    Returns:
        String series of structure tags.
    """

    lb = lookback if lookback is not None else CONFIG.indicator_params.swing_lookback
    sh = df["high"].rolling(lb, center=True).max()
    sl = df["low"].rolling(lb, center=True).min()
    swing_high = df["high"].where(df["high"] == sh)
    swing_low = df["low"].where(df["low"] == sl)
    last_sh = swing_high.ffill()
    last_sl = swing_low.ffill()
    prev_sh = last_sh.shift(1)
    prev_sl = last_sl.shift(1)

    out = pd.Series("", index=df.index, dtype=object)
    hh = swing_high.notna() & (swing_high > prev_sh)
    ll = swing_low.notna() & (swing_low < prev_sl)
    hl = swing_low.notna() & (swing_low > prev_sl)
    lh = swing_high.notna() & (swing_high < prev_sh)
    out = out.mask(hh, "HH")
    out = out.mask(ll, "LL")
    out = out.mask(hl, "HL")
    out = out.mask(lh, "LH")
    return out


def pullback_entry_zone(
    df: pd.DataFrame,
    ema_fast: int = 21,
    ema_slow: int = 50,
) -> pd.Series:
    """
    Flag bars where price is within an ATR band of the fast EMA in trend direction.

    Args:
        df: OHLCV.
        ema_fast: Fast EMA span.
        ema_slow: Slow EMA span.

    Returns:
        Boolean series marking pullback zones.
    """

    cfg = CONFIG.indicator_params
    close = df["close"]
    ef = ema(close, ema_fast)
    es = ema(close, ema_slow)
    atr_s = atr(df["high"], df["low"], df["close"], cfg.atr_period_short)
    trend_up = ef > es
    trend_dn = ef < es
    return (trend_up & (close - ef).abs() <= atr_s) | (
        trend_dn & (close - ef).abs() <= atr_s
    )
