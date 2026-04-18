"""
Market regime classification (trending / ranging / volatile) and regime-aware routing.

Uses ADX, rolling ATR percentile, and Bollinger bandwidth percentile from
``CONFIG.indicator_params`` and ``CONFIG.thresholds``.
"""

from __future__ import annotations

from enum import Enum

import pandas as pd

from forex_bot.config import CONFIG, AppConfig
from forex_bot.indicators._common import atr, percentile_rank_last
from forex_bot.indicators import trend as tr
from forex_bot.indicators.volatility import bollinger_bandwidth, volatility_regime
from forex_bot.strategies._helpers import atr_stop_price, ensure_atr_columns
from forex_bot.strategies.base_strategy import BaseStrategy, Signal, StrategyContext


class MarketRegime(str, Enum):
    """Coarse market state for strategy selection."""

    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"


def classify_regime(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> MarketRegime:
    """
    Classify the latest bar's regime using ADX, ATR percentile, and BB width.

    Priority:
        1. ``VOLATILE`` when rolling ATR regime is ``high``.
        2. ``TRENDING`` when ADX exceeds ``adx_trend_threshold``.
        3. ``RANGING`` when ADX is weak and/or Bollinger width is in the lower
           percentile band (squeeze / consolidation).

    Args:
        df: OHLCV with UTC index.
        config: Optional ``AppConfig`` override.

    Returns:
        :class:`MarketRegime` for the most recent row.
    """

    _ = config
    cfg = CONFIG.indicator_params
    thr = CONFIG.thresholds

    atr_s = atr(df["high"], df["low"], df["close"], cfg.atr_period_short)
    vreg = volatility_regime(atr_s, window=cfg.atr_regime_window)
    vr_last = vreg.iloc[-1]
    if pd.notna(vr_last) and str(vr_last) == "high":
        return MarketRegime.VOLATILE

    adx, _, _ = tr.average_directional_index(df)
    adx_last = float(adx.iloc[-1])

    bbw = bollinger_bandwidth(df["close"])
    bbw_pr = percentile_rank_last(bbw, cfg.atr_regime_window)
    bbw_last = float(bbw_pr.iloc[-1])

    if adx_last >= thr.adx_trend_threshold and bbw_last >= thr.atr_percentile_low / 100.0:
        return MarketRegime.TRENDING

    if adx_last < thr.adx_trend_threshold * 0.6 or bbw_last < thr.atr_percentile_low / 100.0:
        return MarketRegime.RANGING

    return MarketRegime.RANGING


def regime_series(df: pd.DataFrame) -> pd.Series:
    """
    Rolling regime labels (expensive; intended for research / dashboards).

    Args:
        df: OHLCV.

    Returns:
        Series of :class:`MarketRegime` values aligned to ``df.index``.
    """

    out = pd.Series(index=df.index, dtype=object)
    min_len = max(CONFIG.indicator_params.atr_regime_window + 5, 50)
    for i in range(min_len, len(df) + 1):
        sub = df.iloc[:i]
        out.iloc[i - 1] = classify_regime(sub)
    return out


class RegimeSwitcherStrategy(BaseStrategy):
    """
    Route to trend/momentum, mean-reversion/price-action, or SMC by regime.

    Volatile regime scales confidence down (risk layer may further reduce size)
    and widens stops via ATR multiplier.
    """

    def __init__(self) -> None:
        """Compose delegate strategies once."""

        from forex_bot.strategies.mean_reversion_strat import MeanReversionStrategy
        from forex_bot.strategies.momentum_strat import MomentumStrategy
        from forex_bot.strategies.price_action_strat import PriceActionStrategy
        from forex_bot.strategies.smc_strat import SmcStrategy
        from forex_bot.strategies.trend_following_strat import TrendFollowingStrategy

        self._trend = TrendFollowingStrategy()
        self._momentum = MomentumStrategy()
        self._mean_rev = MeanReversionStrategy()
        self._pa = PriceActionStrategy()
        self._smc = SmcStrategy()
        self._volatile_stop_mult: float = 1.5
        self._volatile_conf_mult: float = 0.55

    @property
    def name(self) -> str:
        return "regime_switcher"

    def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
        """Delegate by :func:`classify_regime`; volatile prefers SMC only."""

        df = ensure_atr_columns(ctx.df)
        regime = classify_regime(df)

        if regime == MarketRegime.VOLATILE:
            sig, conf = self._smc.generate_signal(ctx)
            return sig, float(conf * self._volatile_conf_mult)

        if regime == MarketRegime.TRENDING:
            s1, c1 = self._trend.generate_signal(ctx)
            if s1 != Signal.FLAT:
                return s1, c1
            return self._momentum.generate_signal(ctx)

        s2, c2 = self._mean_rev.generate_signal(ctx)
        if s2 != Signal.FLAT:
            return s2, c2
        return self._pa.generate_signal(ctx)

    def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
        """Widen stops in volatile regime."""

        df = ensure_atr_columns(ctx.df)
        atr_s = float(df["atr_short"].iloc[-1])
        regime = classify_regime(df)
        mult = CONFIG.stops_tp.atr_sl_multiplier
        if regime == MarketRegime.VOLATILE:
            mult *= self._volatile_stop_mult
        return atr_stop_price(entry, atr_s, signal, multiplier=mult)

    def get_position_size(
        self,
        ctx: StrategyContext,
        entry: float,
        stop: float,
        signal: Signal,
    ) -> float:
        """Reduce nominal size in volatile regime (before dedicated risk module)."""

        base = super().get_position_size(ctx, entry, stop, signal)
        df = ensure_atr_columns(ctx.df)
        if classify_regime(df) == MarketRegime.VOLATILE:
            return base * 0.5
        return base
