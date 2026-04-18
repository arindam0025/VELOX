"""
Event-driven: flatten around high-impact news; trade breakout after confirmation.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class EventDrivenStrategy(BaseStrategy):
    """Avoid new trades near calendar events; otherwise momentum breakout."""

    @property
    def name(self) -> str:
        return "event_driven"

    def _in_news_blackout(self, ctx: StrategyContext) -> bool:
        """Return True if current bar is inside pre/post event window."""

        if ctx.events_df is None or ctx.events_df.empty:
            return False
        now = pd.Timestamp(ctx.df.index[-1])
        if now.tzinfo is None:
            now = now.tz_localize("UTC")
        else:
            now = now.tz_convert("UTC")
        df_ev = ctx.events_df
        if "time_utc" not in df_ev.columns or "impact" not in df_ev.columns:
            return False
        before = timedelta(minutes=CONFIG.risk.news_blackout_before_minutes)
        after = timedelta(minutes=CONFIG.risk.news_blackout_after_minutes)
        for _, row in df_ev.iterrows():
            if str(row.get("impact", "")).lower() != "high":
                continue
            t = pd.Timestamp(row["time_utc"])
            if t.tzinfo is None:
                t = t.tz_localize("UTC")
            else:
                t = t.tz_convert("UTC")
            if now >= t - before and now <= t + after:
                return True
        return False

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """FLAT in blackout; else 15m-style breakout confirmation."""

        if self._in_news_blackout(ctx):
            return Signal.FLAT, 0.0
        df = ensure_atr_columns(ctx.df)
        if len(df) < 5:
            return Signal.FLAT, 0.0
        o, h, l, c = (
            float(df["open"].iloc[-1]),
            float(df["high"].iloc[-1]),
            float(df["low"].iloc[-1]),
            float(df["close"].iloc[-1]),
        )
        prev = float(df["close"].iloc[-2])
        if c > prev and c > o and (h - l) > float(df["atr_short"].iloc[-1]) * 0.5:
            return Signal.BUY, 0.62
        if c < prev and c < o and (h - l) > float(df["atr_short"].iloc[-1]) * 0.5:
            return Signal.SELL, 0.62
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """Tight ATR stop after volatility events."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
