"""
Volume analytics: spikes, divergence, volume profile, Wyckoff-style heuristics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG, AppConfig
from forex_bot.indicators._common import rolling_zscore, sma


def volume_spikes(
    volume: pd.Series,
    *,
    z_threshold: float | None = None,
    window: int | None = None,
) -> pd.Series:
    """
    Flag bars whose volume Z-score exceeds the configured threshold.

    Args:
        volume: Tick or traded volume series.
        z_threshold: Z-score cut (defaults to ``CONFIG.thresholds.volume_zscore_threshold``).
        window: Rolling window for mean/std.

    Returns:
        Boolean series.
    """

    cfg = CONFIG.indicator_params
    thr = z_threshold if z_threshold is not None else CONFIG.thresholds.volume_zscore_threshold
    w = window if window is not None else cfg.volume_ma_period
    z = rolling_zscore(volume, w)
    return z > thr


def volume_price_divergence(
    close: pd.Series,
    volume: pd.Series,
    lookback: int | None = None,
) -> pd.Series:
    """
    Detect simple divergence: price new high with lower volume or vice versa.

    Args:
        close: Close prices.
        volume: Volume series.
        lookback: Bars to compare extrema.

    Returns:
        Series labels ``bull_div``, ``bear_div``, or empty string.
    """

    lb = lookback if lookback is not None else CONFIG.indicator_params.volume_divergence_lookback
    price_hi = close.rolling(lb).max()
    price_lo = close.rolling(lb).min()
    vol_hi = volume.rolling(lb).max()
    vol_lo = volume.rolling(lb).min()

    bear = (close >= price_hi.shift(1)) & (volume < vol_hi.shift(1))
    bull = (close <= price_lo.shift(1)) & (volume > vol_lo.shift(1))
    out = pd.Series("", index=close.index, dtype=object)
    out = out.mask(bear, "bear_div")
    out = out.mask(bull, "bull_div")
    return out


def volume_profile(
    df: pd.DataFrame,
    *,
    bins: int | None = None,
    window: int | None = None,
    price_col: str = "close",
) -> tuple[float, float, float]:
    """
    Histogram volume by price over a rolling window; return POC, VAH, VAL (70% value area).

    Args:
        df: OHLCV data.
        bins: Histogram bins.
        window: Number of bars.
        price_col: Price reference for binning.

    Returns:
        Tuple ``(poc, vah, val)`` as floats.
    """

    cfg = CONFIG.indicator_params
    b = bins if bins is not None else cfg.volume_profile_bins
    w = window if window is not None else cfg.volume_profile_window
    seg = df[[price_col, "volume"]].dropna().tail(w)
    if seg.empty:
        return float("nan"), float("nan"), float("nan")
    prices = seg[price_col].to_numpy(dtype=float)
    vols = seg["volume"].to_numpy(dtype=float)
    hist, edges = np.histogram(prices, bins=b, weights=vols)
    centers = (edges[:-1] + edges[1:]) / 2.0
    poc_idx = int(np.argmax(hist))
    poc = float(centers[poc_idx])
    total = float(np.sum(hist))
    cum = np.cumsum(hist / total) if total > 0 else np.zeros_like(hist)
    inside = cum <= 0.85
    if not np.any(inside):
        vah = val = poc
    else:
        idxs = np.where(inside)[0]
        vah = float(centers[idxs.max()])
        val = float(centers[idxs.min()])
    return poc, vah, val


def wyckoff_phase_score(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> pd.Series:
    """
    Heuristic Wyckoff labels: accumulation spring/test vs distribution UTAD/LPSY proxies.

    Uses narrowing range + volume contraction/expansion patterns.

    Args:
        df: OHLCV.
        config: Optional config.

    Returns:
        Categorical series: ``accumulation``, ``distribution``, or ``none``.
    """

    cfg = (config or CONFIG).indicator_params
    w = cfg.wyckoff_volume_window
    vol_ma = sma(df["volume"], w)
    rng = df["high"] - df["low"]
    narrow = rng < rng.rolling(w).mean() * 0.7
    spring = (df["low"] < df["low"].rolling(w).min().shift(1)) & (df["close"] > df["open"])
    test = narrow & (df["volume"] < vol_ma)
    utad = (df["high"] > df["high"].rolling(w).max().shift(1)) & (df["close"] < df["open"])
    lpsy = narrow & (df["volume"] < vol_ma.shift(1))

    out = pd.Series("none", index=df.index, dtype=object)
    out = out.mask(spring | test, "accumulation")
    out = out.mask(utad | lpsy, "distribution")
    return out
