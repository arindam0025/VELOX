"""Unit tests for indicator modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.indicators import (
    intermarket,
    ml_signals,
    momentum,
    orderflow,
    price_action,
    sentiment,
    smc,
    trend,
    volatility,
    volume,
)
from forex_bot.indicators._common import atr, ema, macd, rsi, sma, true_range


def test_common_ema_rsi_atr_macd() -> None:
    """EMA/RSI/ATR/MACD helpers produce finite values."""

    t = np.linspace(0, 4, 80)
    s = pd.Series(1.0 + 0.02 * np.sin(t) + 0.001 * t)
    assert ema(s, 10).iloc[-1] > 0
    r = rsi(s, 14)
    assert r.notna().iloc[-1]
    assert 0 < float(r.iloc[-1]) < 100
    h, l, c = s + 0.01, s - 0.01, s
    assert atr(h, l, c, 14).iloc[-1] > 0
    line, sig, hist = macd(s, 12, 26, 9)
    assert np.isfinite(line.iloc[-1])


def test_price_action_pivots_and_patterns(sample_ohlcv: pd.DataFrame) -> None:
    """Pivot and candlestick pattern columns are added."""

    ph, pl = price_action.pivot_high_low(sample_ohlcv["high"], sample_ohlcv["low"], 2)
    assert ph.notna().any() or pl.notna().any()
    pat = price_action.detect_candlestick_patterns(sample_ohlcv)
    assert "pattern_doji" in pat.columns


def test_smc_fvg_and_structure(sample_ohlcv: pd.DataFrame) -> None:
    """SMC utilities run without error."""

    fvgs = smc.detect_fair_value_gaps(sample_ohlcv)
    assert isinstance(fvgs, list)
    bos = smc.break_of_structure(sample_ohlcv)
    assert bos.dtype == int
    choch = smc.change_of_character(bos)
    assert len(choch) == len(sample_ohlcv)
    pd_ = smc.premium_discount_zones(sample_ohlcv)
    assert "zone" in pd_.columns


def test_volume_spike_and_profile(sample_ohlcv: pd.DataFrame) -> None:
    """Volume spike and profile return sensible objects."""

    spikes = volume.volume_spikes(sample_ohlcv["volume"])
    assert spikes.dtype == bool
    poc, vah, val = volume.volume_profile(sample_ohlcv)
    assert poc == poc  # not NaN unless empty


def test_trend_emas_adx(sample_ohlcv: pd.DataFrame) -> None:
    """EMA stack and ADX append columns."""

    emas = trend.add_emas(sample_ohlcv["close"])
    smas = trend.add_smas(sample_ohlcv["close"])
    assert len(emas.columns) > 0 and len(smas.columns) > 0
    adx, pdi, mdi = trend.average_directional_index(sample_ohlcv)
    assert adx.iloc[-1] == adx.iloc[-1]


def test_momentum_rsi_macd_bb(sample_ohlcv: pd.DataFrame) -> None:
    """RSI, MACD bundle, and squeeze run."""

    r = momentum.rsi_series(sample_ohlcv["close"])
    assert 0 <= r.iloc[-1] <= 100
    m = momentum.macd_bundle(sample_ohlcv)
    assert "macd_hist" in m.columns
    sq = momentum.bollinger_squeeze(sample_ohlcv["close"])
    assert sq.dtype == bool


def test_volatility_atr_regime(sample_ohlcv: pd.DataFrame) -> None:
    """ATR dual and regime classification."""

    a = volatility.atr_dual(sample_ohlcv)
    assert "atr_short" in a.columns
    reg = volatility.volatility_regime(a["atr_short"])
    assert reg.iloc[-1] in {"low", "medium", "high"}


def test_orderflow_infer_and_imbalance(sample_ohlcv: pd.DataFrame) -> None:
    """Bid/ask inference and imbalance stay in [-1, 1]."""

    b, a = orderflow.infer_bid_ask_from_ohlcv(sample_ohlcv)
    imb = orderflow.bid_ask_imbalance(b, a)
    assert imb.abs().max() <= 1.0


def test_intermarket_correlation(sample_ohlcv: pd.DataFrame) -> None:
    """Rolling correlation with self is ~1."""

    x = sample_ohlcv["close"]
    corr = intermarket.rolling_return_correlation(x, x, window=20)
    assert corr.iloc[-1] > 0.99


def test_ml_heuristic_signal(sample_ohlcv: pd.DataFrame) -> None:
    """Heuristic ML signal returns dataclass."""

    sig = ml_signals.heuristic_ml_signal(sample_ohlcv)
    assert sig.direction in {"buy", "sell", "flat"}
    assert 0 <= sig.confidence <= 1


def test_sentiment_cot_parse() -> None:
    """COT CSV parsing reads expected columns."""

    csv = "report_date,noncommercial_net,commercial_net\n2025-01-01,1000,-800\n"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cot.csv"
        p.write_text(csv, encoding="utf-8")
        df = sentiment.parse_cot_csv(p)
        assert len(df) == 1
    assert sentiment.retail_contrarian_signal(80) == "fade_longs"


def test_true_range_sma() -> None:
    """True range and SMA basics."""

    h = pd.Series([1.1, 1.2, 1.15])
    l = pd.Series([1.0, 1.1, 1.05])
    c = pd.Series([1.05, 1.15, 1.08])
    tr = true_range(h, l, c)
    assert tr.iloc[1] > 0
    assert sma(c, 2).iloc[-1] > 0


def test_price_action_sr_and_trendline(sample_ohlcv: pd.DataFrame) -> None:
    """S/R table and trendline regression run."""

    df = sample_ohlcv.copy()
    from forex_bot.indicators.volatility import atr_dual

    df = pd.concat([df, atr_dual(df)], axis=1)
    sr = price_action.support_resistance_levels(df)
    assert "level" in sr.columns or sr.empty
    ph, _ = price_action.pivot_high_low(df["high"], df["low"], 2)
    slope, intercept = price_action.linear_regression_trendline(ph)
    assert slope == slope


def test_smc_order_blocks_liquidity(sample_ohlcv: pd.DataFrame) -> None:
    """Order blocks and liquidity helpers."""

    ob = smc.order_blocks(sample_ohlcv)
    assert "ob_direction" in ob.columns
    liq = smc.liquidity_levels(sample_ohlcv)
    assert not liq.empty
    grabs = smc.liquidity_grab(sample_ohlcv, liq)
    assert len(grabs) == len(sample_ohlcv)


def test_volume_divergence_wyckoff(sample_ohlcv: pd.DataFrame) -> None:
    """Volume divergence and Wyckoff labels."""

    div = volume.volume_price_divergence(sample_ohlcv["close"], sample_ohlcv["volume"])
    assert len(div) == len(sample_ohlcv)
    w = volume.wyckoff_phase_score(sample_ohlcv)
    assert w.iloc[-1] in {"none", "accumulation", "distribution"}


def test_trend_structure_pullback(sample_ohlcv: pd.DataFrame) -> None:
    """Market structure labels and pullback zones."""

    ms = trend.market_structure_labels(sample_ohlcv)
    assert len(ms) == len(sample_ohlcv)
    pb = trend.pullback_entry_zone(sample_ohlcv)
    assert pb.dtype == bool


def test_momentum_divergence_breakouts(
    sample_ohlcv: pd.DataFrame,
    session_flags_frame: pd.DataFrame,
) -> None:
    """RSI divergence, range breakout, session breakout."""

    rv = momentum.rsi_series(sample_ohlcv["close"])
    div = momentum.rsi_divergence_flags(sample_ohlcv["close"], rv)
    assert len(div) == len(sample_ohlcv)
    rb = momentum.range_breakout_with_volume(sample_ohlcv)
    assert rb.dtype == bool
    sb = momentum.session_open_breakout(sample_ohlcv, session_flags_frame)
    assert len(sb) == len(sample_ohlcv)


def test_orderflow_delta_dom() -> None:
    """Delta, cumulative divergence, DOM imbalance."""

    b = pd.Series([10.0, 12.0, 8.0, 9.0])
    a = pd.Series([8.0, 9.0, 11.0, 10.0])
    d = orderflow.delta_series(b, a)
    assert d.iloc[0] == 2.0
    c = pd.Series([1.0, 1.01, 0.99, 1.02])
    dd = orderflow.cumulative_delta_divergence(c, d, 2)
    assert len(dd) == len(c)
    levels = [
        orderflow.DomLevel(1.0, 100, 80),
        orderflow.DomLevel(1.0001, 50, 90),
    ]
    imb = orderflow.dom_snapshot_imbalance(levels, depth=2)
    assert -1 <= imb <= 1


def test_volatility_bandwidth(sample_ohlcv: pd.DataFrame) -> None:
    """Bollinger bandwidth series."""

    bw = volatility.bollinger_bandwidth(sample_ohlcv["close"])
    assert np.isfinite(bw.iloc[-1])


def test_intermarket_heatmap(sample_ohlcv: pd.DataFrame) -> None:
    """Pairwise correlation matrix."""

    prices = pd.DataFrame(
        {
            "a": sample_ohlcv["close"],
            "b": sample_ohlcv["close"] * 1.01,
        }
    )
    mat = intermarket.correlation_heatmap_matrix(prices, window=30)
    assert mat.shape == (2, 2)


def test_percentile_rank_and_ml_branches(sample_ohlcv: pd.DataFrame) -> None:
    """Percentile rank helper and ML signal branches."""

    from forex_bot.indicators._common import percentile_rank_last

    s = sample_ohlcv["close"]
    pr = percentile_rank_last(s, 20)
    assert len(pr) == len(s)
    _ = ml_signals.heuristic_ml_signal(sample_ohlcv)
