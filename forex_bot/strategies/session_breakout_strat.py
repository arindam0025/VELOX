"""
Session breakouts: Asian range vs London/NY opens with volume confirmation.
"""

from __future__ import annotations

from forex_bot.data.session_filter import annotate_sessions
from forex_bot.indicators import momentum as mom
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class SessionBreakoutStrategy(BaseStrategy):
    """Breakout of Asian range or session-open impulse."""

    @property
    def name(self) -> str:
        return "session_breakout"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Use momentum session-open and range breakout helpers."""

        df = ensure_atr_columns(ctx.df)
        ann = annotate_sessions(df)
        br = mom.range_breakout_with_volume(df)
        so = mom.session_open_breakout(df, ann)
        if bool(br.iloc[-1]) and float(df["close"].iloc[-1]) > float(df["open"].iloc[-1]):
            return Signal.BUY, 0.66
        if bool(br.iloc[-1]) and float(df["close"].iloc[-1]) < float(df["open"].iloc[-1]):
            return Signal.SELL, 0.66
        if bool(so.iloc[-1]) and float(df["close"].iloc[-1]) > float(df["open"].iloc[-1]):
            return Signal.BUY, 0.6
        if bool(so.iloc[-1]) and float(df["close"].iloc[-1]) < float(df["open"].iloc[-1]):
            return Signal.SELL, 0.6
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR stop beyond range boundary."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
