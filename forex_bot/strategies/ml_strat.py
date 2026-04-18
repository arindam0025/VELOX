"""
ML strategy: uses heuristic / model probability until trained pipeline is attached.
"""

from __future__ import annotations

from forex_bot.config import CONFIG
from forex_bot.indicators import ml_signals
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class MlStrategy(BaseStrategy):
    """Trade when model confidence exceeds ``CONFIG.thresholds.ml_confidence_threshold``."""

    @property
    def name(self) -> str:
        return "ml"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Map heuristic classifier output to BUY/SELL/FLAT."""

        df = ensure_atr_columns(ctx.df)
        out = ml_signals.heuristic_ml_signal(df)
        thr = CONFIG.thresholds.ml_confidence_threshold
        if out.confidence < thr:
            return Signal.FLAT, float(out.confidence)
        if out.direction == "buy":
            return Signal.BUY, float(out.confidence)
        if out.direction == "sell":
            return Signal.SELL, float(out.confidence)
        return Signal.FLAT, float(out.confidence)

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR-based stop."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
