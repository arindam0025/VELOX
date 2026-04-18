"""
Volume + Wyckoff-style accumulation/distribution heuristics.
"""

from __future__ import annotations

from forex_bot.indicators import volume as vol_ind
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class VolumeWyckoffStrategy(BaseStrategy):
    """Spring/test or UTAD/LPSY with volume spike confirmation."""

    @property
    def name(self) -> str:
        return "volume_wyckoff"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Trade reversals when Wyckoff phase and volume spike align."""

        df = ensure_atr_columns(ctx.df)
        phase = vol_ind.wyckoff_phase_score(df).iloc[-1]
        spike = vol_ind.volume_spikes(df["volume"]).iloc[-1]
        close = df["close"]
        up = close.diff().iloc[-1] > 0
        if phase == "accumulation" and spike and up:
            return Signal.BUY, 0.65
        if phase == "distribution" and spike and not up:
            return Signal.SELL, 0.65
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR-based protective stop."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
