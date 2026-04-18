"""
Trend following: EMA stack + ADX filter, pullback to fast EMA.
"""

from __future__ import annotations

from forex_bot.config import CONFIG
from forex_bot.indicators import trend as tr
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class TrendFollowingStrategy(BaseStrategy):
    """EMA 21 vs 50/200 trend with ADX > threshold."""

    @property
    def name(self) -> str:
        return "trend_following"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """BUY in uptrend pullback; SELL in downtrend pullback."""

        df = ensure_atr_columns(ctx.df)
        adx, _, _ = tr.average_directional_index(df)
        if float(adx.iloc[-1]) < CONFIG.thresholds.adx_trend_threshold:
            return Signal.FLAT, 0.0
        ema21 = tr.add_emas(df["close"], (21,))
        ema50 = tr.add_emas(df["close"], (50,))
        e21 = float(ema21["ema_21"].iloc[-1])
        e50 = float(ema50["ema_50"].iloc[-1])
        price = float(df["close"].iloc[-1])
        pb = tr.pullback_entry_zone(df, ema_fast=21, ema_slow=50)
        if e21 > e50 and pb.iloc[-1] and price >= e21 * 0.9999:
            return Signal.BUY, 0.7
        if e21 < e50 and pb.iloc[-1] and price <= e21 * 1.0001:
            return Signal.SELL, 0.7
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """Stop beyond swing using ATR multiple."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
