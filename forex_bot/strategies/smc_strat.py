"""
SMC-style: discount/premium, order block proximity, BOS, CHoCH prerequisite.
"""

from __future__ import annotations

from forex_bot.indicators import smc as smc_ind
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class SmcStrategy(BaseStrategy):
    """Order block + FVG context with CHoCH filter."""

    @property
    def name(self) -> str:
        return "smc"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Align long/short with PD array, BOS, and recent CHoCH."""

        df = ensure_atr_columns(ctx.df)
        bos = smc_ind.break_of_structure(df)
        choch = smc_ind.change_of_character(bos)
        pdz = smc_ind.premium_discount_zones(df)
        zone = str(pdz["zone"].iloc[-1])
        ob = smc_ind.order_blocks(df)
        price = float(df["close"].iloc[-1])
        if not (choch != 0).tail(30).any():
            return Signal.FLAT, 0.0
        bullish_ob = ob["ob_direction"].iloc[-1] == "bullish" and zone == "discount"
        bearish_ob = ob["ob_direction"].iloc[-1] == "bearish" and zone == "premium"
        fvgs = smc_ind.detect_fair_value_gaps(df)
        has_fvg = len(fvgs) > 0 and not fvgs[-1].filled
        if bos.iloc[-1] == 1 and bullish_ob and has_fvg:
            return Signal.BUY, 0.75
        if bos.iloc[-1] == -1 and bearish_ob and has_fvg:
            return Signal.SELL, 0.75
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR stop beyond last swing proxy."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
