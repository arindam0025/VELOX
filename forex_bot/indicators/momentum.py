"""
Momentum: RSI (with divergence), MACD, Bollinger Bands, breakouts, session opens.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG, AppConfig
from forex_bot.indicators._common import atr, bollinger_bands, ema, macd, rsi, sma


def rsi_series(
    close: pd.Series,
    period: int | None = None,
) -> pd.Series:
    """
    RSI with default period from configuration.

    Args:
        close: Close prices.
        period: RSI length.

    Returns:
        RSI series.
    """

    p = period if period is not None else CONFIG.indicator_params.rsi_period
    return rsi(close, p)


def rsi_divergence_flags(
    close: pd.Series,
    rsi_val: pd.Series,
    lookback: int | None = None,
) -> pd.Series:
    """
    Simple RSI divergence: price higher high with RSI lower high (bearish), etc.

    Args:
        close: Close prices.
        rsi_val: RSI series.
        lookback: Comparison window.

    Returns:
        Series with ``bearish``, ``bullish``, or empty string.
    """

    lb = lookback if lookback is not None else CONFIG.indicator_params.rsi_divergence_lookback
    ph = close.rolling(lb).max()
    pl = close.rolling(lb).min()
    rh = rsi_val.rolling(lb).max()
    rl = rsi_val.rolling(lb).min()

    bear = (close >= ph.shift(1)) & (rsi_val < rh.shift(1))
    bull = (close <= pl.shift(1)) & (rsi_val > rl.shift(1))
    out = pd.Series("", index=close.index, dtype=object)
    out = out.mask(bear, "bearish")
    out = out.mask(bull, "bullish")
    return out


def macd_bundle(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append MACD line, signal, and histogram using configured periods.

    Args:
        df: Must include ``close``.

    Returns:
        DataFrame with ``macd``, ``macd_signal``, ``macd_hist``.
    """

    cfg = CONFIG.indicator_params
    line, sig, hist = macd(
        df["close"],
        cfg.macd_fast,
        cfg.macd_slow,
        cfg.macd_signal,
    )
    out = pd.DataFrame(
        {"macd": line, "macd_signal": sig, "macd_hist": hist},
        index=df.index,
    )
    return out


def bollinger_bands_from_config(
    close: pd.Series,
    period: int | None = None,
    num_std: float | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger bands using configured default period and std.

    Args:
        close: Close prices.
        period: SMA window override.
        num_std: Std multiplier override.

    Returns:
        Tuple ``(middle, upper, lower)``.
    """

    cfg = CONFIG.indicator_params
    p = period if period is not None else cfg.bb_period
    ns = num_std if num_std is not None else cfg.bb_std
    return bollinger_bands(close, p, ns)


def bollinger_squeeze(
    close: pd.Series,
    *,
    period: int | None = None,
    bandwidth_pct_window: int | None = None,
) -> pd.Series:
    """
    Bollinger Band width squeeze when bandwidth is in bottom percentile of window.

    Args:
        close: Close prices.
        period: BB period.
        bandwidth_pct_window: Rolling window for percentile rank.

    Returns:
        Boolean series (True when squeezed).
    """

    cfg = CONFIG.indicator_params
    p = period if period is not None else cfg.bb_period
    mid, upper, lower = bollinger_bands_from_config(close, p, cfg.bb_std)
    bw = (upper - lower) / mid.replace(0.0, np.nan)
    w = bandwidth_pct_window if bandwidth_pct_window is not None else cfg.bb_bandwidth_percentile_window
    rank = bw.rolling(w, min_periods=w).apply(
        lambda x: float(np.mean(x <= x[-1])) if len(x) == w else np.nan,
        raw=True,
    )
    return rank < 0.2


def range_breakout_with_volume(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> pd.Series:
    """
    Close breaks N-bar high/low with volume above its moving average.

    Args:
        df: OHLCV.
        config: Optional config.

    Returns:
        Boolean series.
    """

    cfg = (config or CONFIG).indicator_params
    n = cfg.range_breakout_lookback
    vma = sma(df["volume"], cfg.volume_ma_period)
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(n).min().shift(1)
    up = (df["close"] > hi) & (df["volume"] > vma * cfg.session_breakout_volume_ma_ratio)
    dn = (df["close"] < lo) & (df["volume"] > vma * cfg.session_breakout_volume_ma_ratio)
    return up | dn


def session_open_breakout(
    df: pd.DataFrame,
    session_flags: pd.DataFrame,
    *,
    london_col: str = "session_london",
    ny_col: str = "session_new_york",
) -> pd.Series:
    """
    Momentum continuation after London or NY session opens (first bar of session).

    Args:
        df: OHLCV.
        session_flags: Boolean columns from :func:`forex_bot.data.session_filter.annotate_sessions`.
        london_col: Column name for London window.
        ny_col: Column name for New York window.

    Returns:
        Boolean series marking qualifying breakout bars.
    """

    lon = session_flags[london_col].to_numpy(dtype=bool)
    ny = session_flags[ny_col].to_numpy(dtype=bool)
    prev_lon = np.roll(lon, 1)
    prev_lon[0] = False
    prev_ny = np.roll(ny, 1)
    prev_ny[0] = False
    first_lon = pd.Series(lon & ~prev_lon, index=df.index, dtype=bool)
    first_ny = pd.Series(ny & ~prev_ny, index=df.index, dtype=bool)
    atr_s = atr(df["high"], df["low"], df["close"], CONFIG.indicator_params.atr_period_short)
    impulse = (df["close"] - df["open"]).abs() > atr_s * 0.5
    return impulse & (first_lon | first_ny)
