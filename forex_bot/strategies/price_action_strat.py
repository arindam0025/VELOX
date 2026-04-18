"""
Price action: breakout/retest with pattern confirmation and ATR filter.
"""

from __future__ import annotations

import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.data.session_filter import get_session_flags
from forex_bot.indicators import price_action as pa
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class PriceActionStrategy(BaseStrategy):
    """Breakout + retest with pin bar / engulfing; session and ATR filter."""

    @property
    def name(self) -> str:
        return "price_action"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Return BUY/SELL on retest with pattern; FLAT otherwise."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        thr_atr = df["close"].iloc[-1] * 0.0005
        if atr_s < thr_atr:
            return Signal.FLAT, 0.0
        now = df.index[-1].to_pydatetime()
        sess = get_session_flags(now)
        if not (sess.london or sess.new_york):
            return Signal.FLAT, 0.0
        pat = pa.detect_candlestick_patterns(df)
        bull = pat["pattern_bull_engulfing"].iloc[-1] or pat["pattern_hammer"].iloc[-1]
        bear = pat["pattern_bear_engulfing"].iloc[-1] or pat["pattern_shooting_star"].iloc[-1]
        close = df["close"]
        hi20 = close.rolling(20).max().iloc[-2]
        lo20 = close.rolling(20).min().iloc[-2]
        c, p = float(close.iloc[-1]), float(close.iloc[-2])
        if p <= hi20 < c and bull:
            return Signal.BUY, 0.7
        if p >= lo20 > c and bear:
            return Signal.SELL, 0.7
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR-based stop."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)

    def is_valid(self, ctx: StrategyContext) -> bool:
        """Session timing + ATR + spread gate."""

        if not super().is_valid(ctx):
            return False
        df = ensure_atr_columns(ctx.df)
        return float(df["atr_short"].iloc[-1]) > 0
