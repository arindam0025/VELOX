"""
Multi-strategy hybrid: SMC + Volume + Session + Trend with weighted scoring.

Fires only when at least three components agree on direction and the weighted
score meets ``CONFIG.thresholds.multi_strategy_min_score``.
"""

from __future__ import annotations

from forex_bot.config import CONFIG, AppConfig
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext
from forex_bot.strategies.session_breakout_strat import SessionBreakoutStrategy
from forex_bot.strategies.smc_strat import SmcStrategy
from forex_bot.strategies.trend_following_strat import TrendFollowingStrategy
from forex_bot.strategies.volume_strat import VolumeWyckoffStrategy


class MultiStrategyHybrid(BaseStrategy):
    """
    Combine SMC, volume, session breakout, and trend following with fixed weights.

    Weights default from ``CONFIG.thresholds`` (35% / 25% / 20% / 20%).
    """

    def __init__(
        self,
        *,
        smc: SmcStrategy | None = None,
        volume: VolumeWyckoffStrategy | None = None,
        session: SessionBreakoutStrategy | None = None,
        trend: TrendFollowingStrategy | None = None,
        config: AppConfig | None = None,
    ) -> None:
        """
        Build the hybrid with injectable legs for testing.

        Args:
            smc: SMC leg (defaults to new :class:`SmcStrategy`).
            volume: Volume/Wyckoff leg.
            session: Session breakout leg.
            trend: Trend following leg.
            config: Optional config for future use.
        """

        _ = config
        self._smc = smc or SmcStrategy()
        self._volume = volume or VolumeWyckoffStrategy()
        self._session = session or SessionBreakoutStrategy()
        self._trend = trend or TrendFollowingStrategy()

    @property
    def name(self) -> str:
        return "multi_hybrid"

    def _weights(self) -> tuple[tuple[BaseStrategy, float, str], ...]:
        """Return (strategy, weight, label) tuples in fixed order."""

        th = CONFIG.thresholds
        return (
            (self._smc, th.multi_strategy_weight_smc, "smc"),
            (self._volume, th.multi_strategy_weight_volume, "volume"),
            (self._session, th.multi_strategy_weight_session, "session"),
            (self._trend, th.multi_strategy_weight_trend, "trend"),
        )

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """
        Require >=3 legs on the same side; weighted score must clear min threshold.

        The combined score is ``sum(weight_i * conf_i)`` over legs matching the
        majority direction (misaligned legs contribute nothing).
        """

        legs: list[tuple[Signal, float, float]] = []
        for strat, w, _ in self._weights():
            sig, conf = strat.generate_signal(ctx)
            legs.append((sig, conf, w))

        buy_n = sum(1 for s, _, _ in legs if s == Signal.BUY)
        sell_n = sum(1 for s, _, _ in legs if s == Signal.SELL)

        if buy_n >= 3:
            consensus = Signal.BUY
        elif sell_n >= 3:
            consensus = Signal.SELL
        else:
            return Signal.FLAT, 0.0

        combined = sum(w * c for s, c, w in legs if s == consensus)
        min_score = CONFIG.thresholds.multi_strategy_min_score
        if combined < min_score:
            return Signal.FLAT, 0.0
        return consensus, float(min(1.0, combined))

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """ATR stop from primary context (execution may refine)."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        return atr_stop_price(entry, atr_s, signal)

    def component_breakdown(
        self,
        ctx: StrategyContext,
    ) -> list[tuple[str, Signal, float, float]]:
        """
        Diagnostics: per-leg signal, confidence, and weight.

        Args:
            ctx: Strategy context.

        Returns:
            List of ``(label, signal, confidence, weight)``.
        """

        out: list[tuple[str, Signal, float, float]] = []
        for strat, w, label in self._weights():
            sig, conf = strat.generate_signal(ctx)
            out.append((label, sig, conf, w))
        return out
