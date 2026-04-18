"""
Heuristic ML-style signal aggregation until trained models are wired in.

Uses configuration thresholds only; replace internals with ``predictor`` outputs later.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.indicators.momentum import rsi_series
from forex_bot.indicators.trend import add_emas


@dataclass(frozen=True)
class MLSignal:
    """Container for model-like outputs."""

    direction: str
    confidence: float
    features_used: tuple[str, ...]


def heuristic_ml_signal(df: pd.DataFrame) -> MLSignal:
    """
    Combine fast trend (EMA stack) and RSI extremity into a probability-like score.

    Args:
        df: OHLCV with ``close``.

    Returns:
        :class:`MLSignal` with direction and confidence in ``[0, 1]``.
    """

    thr = CONFIG.thresholds.ml_confidence_threshold
    emas = add_emas(df["close"])
    periods = CONFIG.indicator_params.ema_periods
    row = emas.iloc[-1]
    bull_stack = all(
        row[f"ema_{periods[i]}"] > row[f"ema_{periods[i + 1]}"]
        for i in range(len(periods) - 1)
    )
    bear_stack = all(
        row[f"ema_{periods[i]}"] < row[f"ema_{periods[i + 1]}"]
        for i in range(len(periods) - 1)
    )
    rsi_val = float(rsi_series(df["close"]).iloc[-1])
    conf = 0.5
    direction = "flat"
    if bull_stack and rsi_val < 70:
        conf = min(1.0, 0.5 + (70.0 - rsi_val) / 100.0)
        direction = "buy"
    elif bear_stack and rsi_val > 30:
        conf = min(1.0, 0.5 + (rsi_val - 30.0) / 100.0)
        direction = "sell"
    if conf < thr:
        direction = "flat"
    feats = ("ema_stack", "rsi")
    return MLSignal(direction=direction, confidence=float(conf), features_used=feats)
