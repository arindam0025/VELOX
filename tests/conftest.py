"""Pytest fixtures for forex_bot tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Synthetic trending OHLCV with UTC index."""

    n = 120
    rng = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    t = np.linspace(0, 3, n)
    close = 1.1 + 0.001 * np.sin(t) + np.linspace(0, 0.02, n)
    noise = np.random.default_rng(42).normal(0, 0.0002, n)
    close = close + noise
    high = close + 0.0005
    low = close - 0.0005
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    vol = np.random.default_rng(43).integers(100, 1000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=rng,
    )


@pytest.fixture
def session_flags_frame(sample_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """OHLCV with session columns for breakout tests."""

    from forex_bot.data.session_filter import annotate_sessions

    return annotate_sessions(sample_ohlcv)
