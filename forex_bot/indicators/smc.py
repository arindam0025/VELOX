"""
Smart Money Concepts style primitives: OB, FVG, BOS/CHoCH, liquidity, PD arrays.

These are heuristic implementations suitable for research and live filtering;
they are not a substitute for discretionary chart analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from forex_bot.config import CONFIG, AppConfig
from forex_bot.indicators._common import atr


@dataclass(frozen=True)
class FairValueGap:
    """3-candle FVG zone."""

    start_time: pd.Timestamp
    end_time: pd.Timestamp
    low: float
    high: float
    direction: Literal["bullish", "bearish"]
    filled: bool


def _atr_series(df: pd.DataFrame, period: int) -> pd.Series:
    """Compute ATR series for the frame."""

    return atr(df["high"], df["low"], df["close"], period)


def detect_fair_value_gaps(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> list[FairValueGap]:
    """
    Detect 3-candle fair value gaps (imbalances) and track fill status.

    Bullish FVG: low of candle 3 > high of candle 1.
    Bearish FVG: high of candle 3 < low of candle 1.

    Args:
        df: OHLCV with UTC index.
        config: Optional config for ATR ratio filter.

    Returns:
        List of :class:`FairValueGap` objects in chronological order.
    """

    cfg = (config or CONFIG).indicator_params
    atr_s = _atr_series(df, cfg.atr_period_short)
    min_gap = atr_s * cfg.fvg_min_gap_atr_ratio

    out: list[FairValueGap] = []
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    idx = df.index
    for i in range(2, len(df)):
        mg = float(min_gap.iloc[i]) if not np.isnan(min_gap.iloc[i]) else 0.0
        # Bullish gap between bar i-2 and i
        if l[i] > h[i - 2]:
            gap_low = h[i - 2]
            gap_high = l[i]
            if gap_high - gap_low >= mg:
                filled = False
                for j in range(i + 1, len(df)):
                    if l[j] <= gap_low:
                        filled = True
                        break
                out.append(
                    FairValueGap(
                        start_time=idx[i - 2],
                        end_time=idx[i],
                        low=float(gap_low),
                        high=float(gap_high),
                        direction="bullish",
                        filled=filled,
                    )
                )
        # Bearish gap
        if h[i] < l[i - 2]:
            gap_high = l[i - 2]
            gap_low = h[i]
            if gap_high - gap_low >= mg:
                filled = False
                for j in range(i + 1, len(df)):
                    if h[j] >= gap_high:
                        filled = True
                        break
                out.append(
                    FairValueGap(
                        start_time=idx[i - 2],
                        end_time=idx[i],
                        low=float(gap_low),
                        high=float(gap_high),
                        direction="bearish",
                        filled=filled,
                    )
                )
    return out


def swing_points(
    df: pd.DataFrame,
    lookback: int | None = None,
) -> tuple[pd.Series, pd.Series]:
    """
    Swing highs and lows using rolling extrema.

    Args:
        df: OHLCV.
        lookback: Half-window size.

    Returns:
        Tuple of swing high and swing low series (NaN except at swings).
    """

    lb = lookback if lookback is not None else CONFIG.indicator_params.swing_lookback
    sh = df["high"].rolling(window=lb, center=True).max()
    sl = df["low"].rolling(window=lb, center=True).min()
    swing_high = df["high"].where(df["high"] == sh)
    swing_low = df["low"].where(df["low"] == sl)
    return swing_high, swing_low


def break_of_structure(
    df: pd.DataFrame,
    lookback: int | None = None,
) -> pd.Series:
    """
    Label BOS events: close breaks prior swing high (bullish) or swing low (bearish).

    Args:
        df: OHLCV.
        lookback: Swing detection lookback.

    Returns:
        Series with values ``1`` bull BOS, ``-1`` bear BOS, ``0`` none.
    """

    cfg = CONFIG.indicator_params
    lb = lookback if lookback is not None else cfg.bos_structure_lookback
    sh, sl = swing_points(df, lb)
    last_sh = sh.ffill()
    last_sl = sl.ffill()
    bull = (df["close"] > last_sh.shift(1)) & (df["close"].shift(1) <= last_sh.shift(1))
    bear = (df["close"] < last_sl.shift(1)) & (df["close"].shift(1) >= last_sl.shift(1))
    out = pd.Series(0, index=df.index, dtype=int)
    out = out.mask(bull, 1).mask(bear, -1)
    return out


def change_of_character(
    bos: pd.Series,
    confirm: int | None = None,
) -> pd.Series:
    """
    CHoCH: first opposing BOS after a run of same-direction BOS labels.

    Args:
        bos: Output from :func:`break_of_structure`.
        confirm: Bars to confirm flip (reserved for future use).

    Returns:
        Series ``1`` / ``-1`` on CHoCH events, else ``0``.
    """

    _ = confirm
    prev = bos.replace(0, np.nan).ffill().fillna(0).astype(int)
    flip = (bos != 0) & (bos != prev.shift(1))
    return flip.astype(int) * bos


def order_blocks(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> pd.DataFrame:
    """
    Heuristic order blocks: last opposite candle before an impulse leg.

    Args:
        df: OHLCV.
        config: Optional config for impulse ATR multiple.

    Returns:
        DataFrame with columns ``ob_low``, ``ob_high``, ``ob_direction``.
    """

    cfg = (config or CONFIG).indicator_params
    atr_s = _atr_series(df, cfg.atr_period_short)
    impulse = (df["high"] - df["low"]) >= atr_s * cfg.order_block_impulse_atr_ratio

    out = pd.DataFrame(index=df.index)
    out["ob_low"] = np.nan
    out["ob_high"] = np.nan
    out["ob_direction"] = pd.Series("", index=df.index, dtype=object)

    for i in range(1, len(df)):
        if not bool(impulse.iloc[i]):
            continue
        if df["close"].iloc[i] > df["open"].iloc[i]:
            # Bullish impulse: bearish OB at i-1
            if df["close"].iloc[i - 1] < df["open"].iloc[i - 1]:
                out.iloc[i, out.columns.get_loc("ob_low")] = df["low"].iloc[i - 1]
                out.iloc[i, out.columns.get_loc("ob_high")] = df["high"].iloc[i - 1]
                out.iloc[i, out.columns.get_loc("ob_direction")] = "bullish"
        else:
            if df["close"].iloc[i - 1] > df["open"].iloc[i - 1]:
                out.iloc[i, out.columns.get_loc("ob_low")] = df["low"].iloc[i - 1]
                out.iloc[i, out.columns.get_loc("ob_high")] = df["high"].iloc[i - 1]
                out.iloc[i, out.columns.get_loc("ob_direction")] = "bearish"
    return out


def liquidity_levels(
    df: pd.DataFrame,
    *,
    config: AppConfig | None = None,
) -> pd.DataFrame:
    """
    Combine equal highs/lows and round-number grids as liquidity pools.

    Args:
        df: OHLCV with optional ``session_high`` / ``session_low`` columns.
        config: Optional config.

    Returns:
        DataFrame of candidate liquidity prices with ``kind`` labels.
    """

    cfg = (config or CONFIG).indicator_params
    atr_s = _atr_series(df, cfg.atr_period_short)
    tol = float(atr_s.iloc[-1]) * cfg.liquidity_equal_tolerance_atr_ratio

    roll_max = df["high"].rolling(window=7, center=True).max()
    roll_min = df["low"].rolling(window=7, center=True).min()
    eqh = df["high"].where((df["high"] >= roll_max - tol) & (df["high"] <= roll_max + tol))
    eql = df["low"].where((df["low"] <= roll_min + tol) & (df["low"] >= roll_min - tol))

    rows: list[dict[str, float | str]] = []
    last_price = float(df["close"].iloc[-1])
    step_maj = cfg.round_number_step_major
    step_min = cfg.round_number_step_minor
    for k in range(-3, 4):
        rows.append(
            {
                "price": round(last_price / step_maj) * step_maj + k * step_min,
                "kind": "round",
            }
        )
    out = pd.DataFrame(rows)
    eq_series = pd.concat([eqh.dropna(), eql.dropna()])
    out_eq = pd.DataFrame(
        {
            "price": eq_series.values,
            "kind": ["equal_high_low"] * len(eq_series),
        }
    )
    return pd.concat([out, out_eq], ignore_index=True)


def premium_discount_zones(
    df: pd.DataFrame,
    lookback: int | None = None,
) -> pd.DataFrame:
    """
    Map price into premium/discount vs 50% of recent swing range (Fib 0.5).

    Args:
        df: OHLCV.
        lookback: Range for swing high/low.

    Returns:
        DataFrame with ``swing_high``, ``swing_low``, ``equilibrium``, ``zone``.
    """

    lb = lookback if lookback is not None else CONFIG.indicator_params.swing_lookback
    sh = df["high"].rolling(lb).max()
    sl = df["low"].rolling(lb).min()
    eq = (sh + sl) / 2.0
    zone = pd.Series("discount", index=df.index)
    zone = zone.mask(df["close"] > eq, "premium")
    zone = zone.mask(np.isclose(df["close"], eq), "equilibrium")
    out = pd.DataFrame({"swing_high": sh, "swing_low": sl, "equilibrium": eq, "zone": zone})
    return out


def liquidity_grab(
    df: pd.DataFrame,
    levels: pd.DataFrame,
) -> pd.Series:
    """
    Detect wick beyond a liquidity level followed by reversal (2-bar confirmation).

    Args:
        df: OHLCV.
        levels: Output of :func:`liquidity_levels` with ``price`` column.

    Returns:
        Boolean series marking liquidity grab candles.
    """

    if levels.empty or "price" not in levels.columns:
        return pd.Series(False, index=df.index)

    grabs = pd.Series(False, index=df.index)
    prices = levels["price"].astype(float).unique()
    for p in prices:
        wicked_above = (df["high"] > p) & (df["close"] < p)
        wicked_below = (df["low"] < p) & (df["close"] > p)
        rev = (df["close"] < df["open"]) | (df["close"] > df["open"])
        grabs = grabs | ((wicked_above | wicked_below) & rev)
    return grabs
