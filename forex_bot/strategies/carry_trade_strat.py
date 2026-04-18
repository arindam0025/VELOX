"""
Carry trade: favor long high-yield currencies vs low-yield when trend agrees.
"""

from __future__ import annotations

from forex_bot.config import CONFIG
from forex_bot.indicators import trend as tr
from forex_bot.strategies._helpers import atr_stop_price, carry_yield_diff_for_pair, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class CarryTradeStrategy(BaseStrategy):
    """Position in direction of positive carry with EMA trend confirmation."""

    @property
    def name(self) -> str:
        return "carry_trade"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """BUY if carry positive and uptrend; SELL if carry negative and downtrend."""

        df = ensure_atr_columns(ctx.df)
        cy = carry_yield_diff_for_pair(
            ctx.instrument,
            CONFIG.carry_yields.annual_yield_percent_by_ccy,
        )
        ema21 = tr.add_emas(df["close"], (21,))
        ema50 = tr.add_emas(df["close"], (50,))
        e21 = float(ema21["ema_21"].iloc[-1])
        e50 = float(ema50["ema_50"].iloc[-1])
        if cy > 0.25 and e21 > e50:
            return Signal.BUY, min(1.0, 0.5 + cy / 10.0)
        if cy < -0.25 and e21 < e50:
            return Signal.SELL, min(1.0, 0.5 + abs(cy) / 10.0)
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """Wide ATR stop; carry horizons are longer."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_long"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal, multiplier=CONFIG.stops_tp.atr_sl_multiplier * 1.2)
