"""
Order flow proxies when bid/ask or tape data is available.

Without L2 data, many functions return NaN-filled series.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from forex_bot.config import CONFIG


@dataclass(frozen=True)
class DomLevel:
    """Single depth-of-market price level."""

    price: float
    bid_size: float
    ask_size: float


def bid_ask_imbalance(
    bid_vol: pd.Series,
    ask_vol: pd.Series,
) -> pd.Series:
    """
    Compute (bid - ask) / (bid + ask) imbalance in [-1, 1].

    Args:
        bid_vol: Aggressive buy volume (or bid-side liquidity consumed).
        ask_vol: Aggressive sell volume.

    Returns:
        Imbalance series.
    """

    denom = (bid_vol + ask_vol).replace(0.0, np.nan)
    return (bid_vol - ask_vol) / denom


def delta_series(
    bid_vol: pd.Series,
    ask_vol: pd.Series,
) -> pd.Series:
    """
    Per-bar delta (buy volume minus sell volume).

    Args:
        bid_vol: Buy volume.
        ask_vol: Sell volume.

    Returns:
        Delta series.
    """

    return bid_vol - ask_vol


def cumulative_delta_divergence(
    close: pd.Series,
    delta: pd.Series,
    lookback: int = 10,
) -> pd.Series:
    """
    Flag bars where price trend disagrees with cumulative delta slope.

    Args:
        close: Close prices.
        delta: Per-bar delta.
        lookback: Bars for slope comparison.

    Returns:
        Boolean series when divergence is detected.
    """

    cd = delta.cumsum()
    price_slope = close.diff(lookback)
    delta_slope = cd.diff(lookback)
    return (price_slope * delta_slope) < 0


def dom_snapshot_imbalance(levels: list[DomLevel], *, depth: int | None = None) -> float:
    """
    Aggregate bid/ask size imbalance across the top DOM levels.

    Args:
        levels: Price levels nearest touch.
        depth: Number of levels to include (defaults to ``CONFIG``).

    Returns:
        Scalar imbalance in [-1, 1].
    """

    d = depth if depth is not None else CONFIG.indicator_params.dom_imbalance_levels
    top = levels[:d]
    if not top:
        return float("nan")
    bid = sum(x.bid_size for x in top)
    ask = sum(x.ask_size for x in top)
    if bid + ask == 0:
        return float("nan")
    return (bid - ask) / (bid + ask)


def infer_bid_ask_from_ohlcv(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    Rough buy/sell volume split using close location within the bar (fallback only).

    Args:
        df: OHLCV with ``volume``.

    Returns:
        Tuple ``(buy_volume, sell_volume)`` estimated per bar.
    """

    rng = (df["high"] - df["low"]).replace(0.0, np.nan)
    t = (df["close"] - df["low"]) / rng
    t = t.clip(0.0, 1.0).fillna(0.5)
    buy = df["volume"] * t
    sell = df["volume"] * (1.0 - t)
    return buy, sell
