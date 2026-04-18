"""
Mean reversion: RSI extremes at range extremes with Bollinger touch.
"""

from __future__ import annotations

from forex_bot.config import CONFIG
from forex_bot.indicators import momentum as mom
from forex_bot.indicators import trend as tr
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class MeanReversionStrategy(BaseStrategy):
    """Fade RSI extremes toward EMA 21 / mean reversion."""

    @property
    def name(self) -> str:
        return "mean_reversion"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Buy oversold + lower BB; sell overbought + upper BB."""

        df = ensure_atr_columns(ctx.df)
        rsi = mom.rsi_series(df["close"])
        mid, upper, lower = mom.bollinger_bands_from_config(df["close"])
        r = float(rsi.iloc[-1])
        c = float(df["close"].iloc[-1])
        th = CONFIG.thresholds
        if r < th.rsi_oversold and c <= float(lower.iloc[-1]) * 1.0001:
            return Signal.BUY, 0.72
        if r > th.rsi_overbought and c >= float(upper.iloc[-1]) * 0.9999:
            return Signal.SELL, 0.72
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR-based stop beyond swing."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)

    def get_take_profit(
        self,
        ctx: StrategyContext,
        entry: float,
        signal: Signal,
    ) -> float | list[float]:
        """Target mid-band / EMA 21 as single TP proxy."""

        df = ensure_atr_columns(ctx.df)
        ema21 = tr.add_emas(df["close"], (21,))
        tgt = float(ema21["ema_21"].iloc[-1])
        return tgt
