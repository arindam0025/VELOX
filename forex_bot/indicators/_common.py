"""
Shared numpy/pandas utilities for indicator calculations.

All tunable lengths come from ``CONFIG.indicator_params`` in calling modules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    """
    Exponential moving average (pandas ``ewm`` with ``adjust=False``).

    Args:
        series: Input series.
        span: EMA span.

    Returns:
        EMA series aligned to ``series`` index.
    """

    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    """
    Simple moving average.

    Args:
        series: Input series.
        window: Rolling window length.

    Returns:
        SMA series.
    """

    return series.rolling(window=window, min_periods=window).mean()


def true_range(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """
    True range as max of high-low, |high-prev_close|, |low-prev_close|.

    Args:
        high: High prices.
        low: Low prices.
        close: Close prices.

    Returns:
        True range series (first row NaN where undefined).
    """

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int,
) -> pd.Series:
    """
    Average true range (Wilder-style smoothing via ``ewm``).

    Args:
        high: High prices.
        low: Low prices.
        close: Close prices.
        period: ATR lookback.

    Returns:
        ATR series.
    """

    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int) -> pd.Series:
    """
    Relative Strength Index (Wilder smoothing).

    Args:
        close: Close prices.
        period: RSI length.

    Returns:
        RSI in [0, 100] with NaNs during warm-up.
    """

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out


def bollinger_bands(
    close: pd.Series,
    period: int,
    num_std: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger middle / upper / lower using SMA and rolling std.

    Args:
        close: Close prices.
        period: SMA window.
        num_std: Standard deviation multiplier.

    Returns:
        Tuple ``(middle, upper, lower)``.
    """

    mid = sma(close, period)
    std = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def macd(
    close: pd.Series,
    fast: int,
    slow: int,
    signal: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD line, signal line, and histogram.

    Args:
        close: Close prices.
        fast: Fast EMA span.
        slow: Slow EMA span.
        signal: Signal EMA span.

    Returns:
        Tuple ``(macd_line, signal_line, histogram)``.
    """

    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    line = ema_fast - ema_slow
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def typical_price(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """
    Typical price (H+L+C)/3.

    Args:
        high: High prices.
        low: Low prices.
        close: Close prices.

    Returns:
        Typical price series.
    """

    return (high + low + close) / 3.0


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling Z-score using sample std (ddof=0).

    Args:
        series: Input series.
        window: Rolling window.

    Returns:
        Z-score series.
    """

    m = series.rolling(window=window, min_periods=window).mean()
    s = series.rolling(window=window, min_periods=window).std(ddof=0)
    return (series - m) / s.replace(0.0, np.nan)


def percentile_rank_last(series: pd.Series, window: int) -> pd.Series:
    """
    Rolling percentile rank of the last value within the window [0,1].

    Args:
        series: Input series.
        window: Lookback window.

    Returns:
        Percentile rank series.
    """

    def _rank_last(arr: np.ndarray) -> float:
        if np.any(np.isnan(arr)):
            return np.nan
        x = arr[-1]
        return float(np.mean(arr <= x))

    return series.rolling(window=window, min_periods=window).apply(
        _rank_last, raw=True
    )
