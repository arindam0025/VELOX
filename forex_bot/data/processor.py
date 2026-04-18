"""
OHLCV cleaning, resampling, and normalization helpers.

All series are expected to use a UTC DatetimeIndex to avoid session ambiguity.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from forex_bot.config import Timeframe


def ensure_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the DataFrame has a sorted UTC DatetimeIndex.

    Args:
        df: Input frame with a DatetimeIndex or a column named ``timestamp``.

    Returns:
        Copy with a monotonic increasing UTC index named ``time`` (index).
    """

    out = df.copy()
    if out.empty and isinstance(out.index, pd.DatetimeIndex):
        if out.index.tz is None:
            out.index = out.index.tz_localize("UTC")
        else:
            out.index = out.index.tz_convert("UTC")
        out.index.name = "time"
        return out.sort_index()
    if isinstance(out.index, pd.DatetimeIndex):
        idx = out.index
    elif "timestamp" in out.columns:
        idx = pd.DatetimeIndex(pd.to_datetime(out["timestamp"], utc=True))
        out = out.drop(columns=["timestamp"])
    else:
        raise ValueError("DataFrame must have DatetimeIndex or 'timestamp' column.")

    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out.index = idx
    out = out.sort_index()
    out.index.name = "time"
    return out


def clean_ohlcv(
    df: pd.DataFrame,
    *,
    drop_zero_volume: bool = True,
    fix_ohlc: bool = True,
) -> pd.DataFrame:
    """
    Drop invalid rows and optionally enforce OHLC consistency.

    Args:
        df: OHLCV-like frame with columns open, high, low, close.
        drop_zero_volume: Remove rows where ``volume`` is 0 if column exists.
        fix_ohlc: Clamp high/low to contain open/close extrema.

    Returns:
        Cleaned copy; may be empty if all rows invalid.
    """

    required = ("open", "high", "low", "close")
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")

    out = df.copy()
    out = out[~out[list(required)].isna().any(axis=1)]
    for col in required:
        out = out[out[col] > 0]
    if drop_zero_volume and "volume" in out.columns:
        out = out[out["volume"] > 0]
    if fix_ohlc:
        o, h, l, c = out["open"], out["high"], out["low"], out["close"]
        out["high"] = np.maximum.reduce([h, o, c])
        out["low"] = np.minimum.reduce([l, o, c])
    return out


def _timeframe_to_pandas_rule(tf: Timeframe) -> str:
    """Map internal timeframe enum to pandas offset alias."""

    mapping: dict[Timeframe, str] = {
        Timeframe.M1: "1min",
        Timeframe.M5: "5min",
        Timeframe.M15: "15min",
        Timeframe.M30: "30min",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1D",
    }
    if tf not in mapping:
        raise ValueError(f"Unsupported timeframe for resampling: {tf}")
    return mapping[tf]


def resample_ohlcv(df: pd.DataFrame, target: Timeframe) -> pd.DataFrame:
    """
    Resample OHLCV bars to ``target`` using standard aggregation rules.

    Args:
        df: OHLCV with UTC DatetimeIndex.
        target: Destination timeframe.

    Returns:
        Resampled OHLCV; volume is summed when present.
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex.")
    rule = _timeframe_to_pandas_rule(target)
    agg: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    }
    if "volume" in df.columns:
        agg["volume"] = "sum"
    out = df.resample(rule, label="left", closed="left").agg(agg)
    out = out.dropna(how="any")
    return out


NormalizationMethod = Literal["returns", "log_returns", "zscore"]


def normalize_ohlcv(
    df: pd.DataFrame,
    column: str = "close",
    method: NormalizationMethod = "returns",
    *,
    zscore_window: int = 50,
) -> pd.Series:
    """
    Build a normalized series from a price column for ML or cross-asset work.

    Args:
        df: Input frame containing ``column``.
        column: Price column to normalize (typically ``close``).
        method: ``returns``, ``log_returns``, or rolling ``zscore``.
        zscore_window: Rolling window for z-score when ``method`` is ``zscore``.

    Returns:
        A ``pd.Series`` aligned to ``df.index`` (with NaNs where undefined).
    """

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found.")
    price = df[column].astype(float)
    if method == "returns":
        return price.pct_change()
    if method == "log_returns":
        return np.log(price).diff()
    if method == "zscore":
        roll = price.rolling(window=zscore_window, min_periods=zscore_window)
        return (price - roll.mean()) / roll.std(ddof=0)
    raise ValueError(f"Unknown normalization method: {method}")
