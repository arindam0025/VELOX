"""
Shared helpers for strategy modules (pip size, enriched OHLCV).
"""

from __future__ import annotations

import pandas as pd

from forex_bot.config import CONFIG, AppConfig
from forex_bot.strategies.base_strategy import Signal
from forex_bot.indicators.volatility import atr_dual


def pip_size_for_instrument(instrument: str, config: AppConfig | None = None) -> float:
    """
    Return pip size for ``instrument`` using configured FX conventions.

    Args:
        instrument: Broker pair symbol (e.g. ``EUR_USD``, ``USD_JPY``).
        config: Optional ``AppConfig`` override.

    Returns:
        Pip size in price units.
    """

    cfg = config or CONFIG
    if "JPY" in instrument.upper():
        return cfg.forex_convention.pip_size_jpy
    return cfg.forex_convention.pip_size_non_jpy


def ensure_atr_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return ``df`` with ``atr_short`` / ``atr_long`` attached if missing.

    Args:
        df: OHLCV input.

    Returns:
        Enriched copy or original if already present.
    """

    if "atr_short" in df.columns and "atr_long" in df.columns:
        return df
    return enrich_ohlcv(df)


def enrich_ohlcv(df: pd.DataFrame, config: AppConfig | None = None) -> pd.DataFrame:
    """
    Attach ``atr_short`` / ``atr_long`` columns required by several strategies.

    Args:
        df: OHLCV DataFrame.
        config: Unused; reserved for future indicator selection.

    Returns:
        Copy with ATR columns merged on index.
    """

    _ = config
    a = atr_dual(df)
    return pd.concat([df, a], axis=1)


def parse_instrument_currencies(instrument: str) -> tuple[str, str]:
    """
    Split ``BASE_QUOTE`` into (base_ccy, quote_ccy) ISO codes.

    Args:
        instrument: Underscore-separated pair.

    Returns:
        Tuple of two 3-letter currency codes.
    """

    parts = instrument.split("_")
    if len(parts) != 2:
        raise ValueError(f"Invalid instrument: {instrument!r}")
    return parts[0].upper(), parts[1].upper()


def atr_stop_price(
    entry: float,
    atr_val: float,
    signal: Signal,
    multiplier: float | None = None,
) -> float:
    """
    Place a stop ``multiplier * ATR`` away from ``entry`` in the adverse direction.

    Args:
        entry: Entry price.
        atr_val: ATR in price units.
        signal: Intended trade direction.
        multiplier: ATR multiple (defaults to ``CONFIG.stops_tp.atr_sl_multiplier``).

    Returns:
        Stop price.
    """

    m = multiplier if multiplier is not None else CONFIG.stops_tp.atr_sl_multiplier
    if signal == Signal.BUY:
        return float(entry - m * atr_val)
    if signal == Signal.SELL:
        return float(entry + m * atr_val)
    return float(entry)


def carry_yield_diff_for_pair(
    instrument: str,
    yields: dict[str, float] | None = None,
) -> float:
    """
    Approximate annualized carry in % for a long spot position (base vs quote).

    Positive means long base / short quote earns positive carry on rate differential.

    Args:
        instrument: ``BASE_QUOTE`` symbol.
        yields: Currency -> annual %; defaults to ``CONFIG.carry_yields``.

    Returns:
        Yield difference ``r_base - r_quote`` in percent per year.
    """

    ymap = yields if yields is not None else CONFIG.carry_yields.annual_yield_percent_by_ccy
    base, quote = parse_instrument_currencies(instrument)
    rb = float(ymap.get(base, 0.0))
    rq = float(ymap.get(quote, 0.0))
    return rb - rq
