"""
Momentum: MACD histogram turn + RSI band filter.
"""

from __future__ import annotations

from forex_bot.config import CONFIG
from forex_bot.indicators import momentum as mom
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class MomentumStrategy(BaseStrategy):
    """MACD histogram expansion with RSI not extreme opposite."""

    @property
    def name(self) -> str:
        return "momentum"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Histogram cross with RSI confirmation."""

        df = ensure_atr_columns(ctx.df)
        m = mom.macd_bundle(df)
        hist = m["macd_hist"]
        rsi = mom.rsi_series(df["close"])
        h0, h1 = float(hist.iloc[-1]), float(hist.iloc[-2])
        r = float(rsi.iloc[-1])
        thr = CONFIG.thresholds
        if h0 > 0 and h1 <= 0 and thr.rsi_oversold < r < 85:
            return Signal.BUY, 0.68
        if h0 < 0 and h1 >= 0 and 15 < r < thr.rsi_overbought:
            return Signal.SELL, 0.68
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR stop."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
