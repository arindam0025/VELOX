"""
Statistical arbitrage: cointegration-style spread Z-score between two FX legs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class StatisticalArbitrageStrategy(BaseStrategy):
    """Pairs trade when spread Z exceeds configured entry threshold."""

    @property
    def name(self) -> str:
        return "statistical_arbitrage"

    def _spread_z(self, y: pd.Series, x: pd.Series, window: int) -> float:
        """Rolling beta hedge ratio and Z-score of the residual spread."""

        y = y.astype(float)
        x = x.astype(float)
        cov = (y * x).rolling(window).mean() - y.rolling(window).mean() * x.rolling(window).mean()
        var_x = x.rolling(window).var()
        beta = cov / var_x.replace(0.0, np.nan)
        spread = y - beta * x
        z = (spread - spread.rolling(window).mean()) / spread.rolling(window).std().replace(0.0, np.nan)
        return float(z.iloc[-1])

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Long/short spread when |Z| exceeds ``stat_arb_z_entry``."""

        cfg = CONFIG.strategy_defaults
        leg_a = ctx.auxiliary_frames.get(cfg.stat_arb_leg_a)
        leg_b = ctx.auxiliary_frames.get(cfg.stat_arb_leg_b)
        if leg_a is None or leg_b is None or len(leg_a) < 40 or len(leg_b) < 40:
            return Signal.FLAT, 0.0
        y = leg_a["close"].astype(float)
        x = leg_b["close"].astype(float)
        n = min(len(y), len(x))
        y = y.iloc[-n:]
        x = x.iloc[-n:]
        z = self._spread_z(y, x, min(60, n - 1))
        z_thr = CONFIG.thresholds.stat_arb_z_entry
        conf = min(1.0, abs(z) / (z_thr * 2))
        if z > z_thr:
            return Signal.SELL, conf
        if z < -z_thr:
            return Signal.BUY, conf
        return Signal.FLAT, 0.0

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """Use primary leg ATR for stop distance on the anchor leg."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)
