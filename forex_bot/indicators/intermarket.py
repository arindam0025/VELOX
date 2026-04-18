"""
Intermarket relationships: rolling correlations of asset returns.
"""

from __future__ import annotations

import pandas as pd

from forex_bot.config import CONFIG


def rolling_return_correlation(
    a: pd.Series,
    b: pd.Series,
    window: int | None = None,
) -> pd.Series:
    """
    Rolling Pearson correlation of aligned simple returns.

    Args:
        a: Price series for asset A.
        b: Price series for asset B (aligned index with ``a``).
        window: Rolling window in bars.

    Returns:
        Correlation series.
    """

    w = window if window is not None else CONFIG.indicator_params.intermarket_rolling_window
    ra = a.pct_change()
    rb = b.pct_change()
    return ra.rolling(w).corr(rb)


def correlation_heatmap_matrix(
    prices: pd.DataFrame,
    window: int | None = None,
) -> pd.DataFrame:
    """
    Pairwise rolling correlation matrix using the last window of returns.

    Args:
        prices: Columns are tickers, index is time.
        window: Return correlation window.

    Returns:
        Square correlation DataFrame for the most recent complete window.
    """

    w = window if window is not None else CONFIG.indicator_params.intermarket_rolling_window
    rets = prices.pct_change()
    tail = rets.dropna().tail(w)
    return tail.corr()
