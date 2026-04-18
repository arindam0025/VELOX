"""Tests for strategy base class and concrete strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from forex_bot.config import Timeframe
from forex_bot.strategies import (
    CarryTradeStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    PriceActionStrategy,
    Signal,
    StatisticalArbitrageStrategy,
    StrategyContext,
    TrendFollowingStrategy,
)
from forex_bot.strategies._helpers import pip_size_for_instrument


@pytest.fixture
def ctx(sample_ohlcv: pd.DataFrame) -> StrategyContext:
    """Build a strategy context from synthetic OHLCV."""

    from forex_bot.strategies._helpers import ensure_atr_columns

    df = ensure_atr_columns(sample_ohlcv)
    return StrategyContext(
        instrument="EUR_USD",
        timeframe=Timeframe.H1,
        df=df,
        account_equity=100_000.0,
        spread=0.00002,
        pip_size=pip_size_for_instrument("EUR_USD"),
        avg_spread=0.00002,
    )


def test_base_position_size_and_tp(ctx: StrategyContext) -> None:
    """Risk-based size and default TP list."""

    strat = MeanReversionStrategy()
    sig, conf = strat.generate_signal(ctx)
    assert sig in (Signal.BUY, Signal.SELL, Signal.FLAT)
    assert 0 <= conf <= 1
    entry = float(ctx.df["close"].iloc[-1])
    if sig != Signal.FLAT:
        sl = strat.get_stop_loss(ctx, entry, sig)
        tp = strat.get_take_profit(ctx, entry, sig)
        assert sl != entry or sig == Signal.FLAT
        sz = strat.get_position_size(ctx, entry, sl, sig)
        assert sz >= 0


def test_stat_arb_requires_auxiliary_frames(ctx: StrategyContext) -> None:
    """Stat arb returns flat without two legs."""

    strat = StatisticalArbitrageStrategy()
    sig, conf = strat.generate_signal(ctx)
    assert sig == Signal.FLAT
    assert conf == 0.0


def test_stat_arb_with_legs(ctx: StrategyContext) -> None:
    """Stat arb runs with aligned auxiliary frames."""

    strat = StatisticalArbitrageStrategy()
    y = ctx.df["close"].copy()
    x = y * 1.0003 + np.random.default_rng(0).normal(0, 1e-5, len(y))
    aux = {
        "EUR_USD": pd.DataFrame({"close": y}, index=ctx.df.index),
        "GBP_USD": pd.DataFrame({"close": x}, index=ctx.df.index),
    }
    ctx2 = StrategyContext(
        instrument=ctx.instrument,
        timeframe=ctx.timeframe,
        df=ctx.df,
        account_equity=ctx.account_equity,
        spread=ctx.spread,
        pip_size=ctx.pip_size,
        auxiliary_frames=aux,
    )
    sig, conf = strat.generate_signal(ctx2)
    assert sig in (Signal.BUY, Signal.SELL, Signal.FLAT)


def test_strategies_smoke(ctx: StrategyContext) -> None:
    """Each listed strategy exposes API without raising."""

    for cls in (
        PriceActionStrategy,
        TrendFollowingStrategy,
        MomentumStrategy,
        CarryTradeStrategy,
    ):
        s = cls()
        sig, c = s.generate_signal(ctx)
        assert isinstance(sig, Signal)
        assert 0 <= c <= 1
        assert isinstance(s.is_valid(ctx), bool)
