"""Tests for regime detector and multi-strategy hybrid."""

from __future__ import annotations

import pandas as pd

from forex_bot.config import Timeframe
from forex_bot.strategies.base_strategy import Signal, StrategyContext
from forex_bot.strategies.multi_strategy import MultiStrategyHybrid
from forex_bot.strategies.regime_detector import (
    MarketRegime,
    RegimeSwitcherStrategy,
    classify_regime,
)
from forex_bot.strategies._helpers import pip_size_for_instrument, ensure_atr_columns


def test_classify_regime_returns_market_regime(sample_ohlcv: pd.DataFrame) -> None:
    """Regime classifier returns a valid enum member."""

    r = classify_regime(sample_ohlcv)
    assert r in {MarketRegime.TRENDING, MarketRegime.RANGING, MarketRegime.VOLATILE}


def test_regime_switcher_smoke(sample_ohlcv: pd.DataFrame) -> None:
    """Regime switcher produces API-compliant output."""

    df = ensure_atr_columns(sample_ohlcv)
    ctx = StrategyContext(
        instrument="EUR_USD",
        timeframe=Timeframe.H1,
        df=df,
        account_equity=100_000.0,
        spread=0.00002,
        pip_size=pip_size_for_instrument("EUR_USD"),
        avg_spread=0.00002,
    )
    s = RegimeSwitcherStrategy()
    sig, conf = s.generate_signal(ctx)
    assert sig in (Signal.BUY, Signal.SELL, Signal.FLAT)
    assert 0 <= conf <= 1
    entry = float(df["close"].iloc[-1])
    if sig != Signal.FLAT:
        sl = s.get_stop_loss(ctx, entry, sig)
        assert sl != entry or sig == Signal.FLAT
        sz = s.get_position_size(ctx, entry, sl, sig)
        assert sz >= 0


def test_multi_hybrid_weights_sum() -> None:
    """Configured multi-strategy weights sum to ~1.0."""

    from forex_bot.config import CONFIG

    th = CONFIG.thresholds
    s = (
        th.multi_strategy_weight_smc
        + th.multi_strategy_weight_volume
        + th.multi_strategy_weight_session
        + th.multi_strategy_weight_trend
    )
    assert abs(s - 1.0) < 1e-6


def test_multi_hybrid_with_mock_legs() -> None:
    """Hybrid respects 3-of-4 alignment and weighted score."""

    from forex_bot.strategies.base_strategy import BaseStrategy

    class FixedSignal(BaseStrategy):
        def __init__(self, sig: Signal, c: float) -> None:
            self._sig = sig
            self._c = c

        @property
        def name(self) -> str:
            return "fixed"

        def generate_signal(self, ctx: StrategyContext) -> tuple[Signal, float]:
            return self._sig, self._c

        def get_stop_loss(self, ctx: StrategyContext, entry: float, signal: Signal) -> float:
            return entry - 0.01 if signal == Signal.BUY else entry + 0.01

    df = pd.DataFrame(
        {
            "open": [1.0] * 80,
            "high": [1.01] * 80,
            "low": [0.99] * 80,
            "close": [1.0] * 80,
            "volume": [1000.0] * 80,
        },
        index=pd.date_range("2025-01-01", periods=80, freq="1h", tz="UTC"),
    )
    df = ensure_atr_columns(df)
    ctx = StrategyContext(
        instrument="EUR_USD",
        timeframe=Timeframe.H1,
        df=df,
        account_equity=100_000.0,
        spread=0.00002,
        pip_size=pip_size_for_instrument("EUR_USD"),
    )
    buy = Signal.BUY
    hi = 0.85
    smc = FixedSignal(buy, hi)
    vol = FixedSignal(buy, hi)
    ses = FixedSignal(buy, hi)
    trd = FixedSignal(buy, hi)
    m = MultiStrategyHybrid(smc=smc, volume=vol, session=ses, trend=trd)
    sig, conf = m.generate_signal(ctx)
    assert sig == Signal.BUY
    assert conf >= 0.65
