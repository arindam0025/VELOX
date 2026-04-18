"""
Forex signal generation.

Builds three practical directional models from the engineered features:
trend following, mean reversion, and breakout.
"""

from __future__ import annotations

import os

import pandas as pd

from forex_config import DATA_DIR, FOREX_PAIRS, SIGNALS_DIR, ensure_directories


def _shift_signal(signal: pd.Series) -> pd.Series:
    """Shift by one bar so today's close-based logic executes on the next bar."""

    return signal.shift(1).fillna(0).astype(int)


def _position_signal(
    long_entry: pd.Series,
    short_entry: pd.Series,
    exit_long: pd.Series,
    exit_short: pd.Series,
    *,
    confirm_bars: int,
    min_hold_bars: int,
    name: str,
) -> pd.Series:
    """
    Build a cleaner directional signal using confirmation + minimum hold.

    This suppresses one-bar flips that create noisy long/short churn.
    """

    signal = pd.Series(0, index=long_entry.index, name=name, dtype=int)
    position = 0
    hold_bars = 0
    long_count = 0
    short_count = 0

    for i in range(len(signal)):
        le = bool(long_entry.iloc[i])
        se = bool(short_entry.iloc[i])
        xl = bool(exit_long.iloc[i])
        xs = bool(exit_short.iloc[i])

        if position == 0:
            long_count = long_count + 1 if le else 0
            short_count = short_count + 1 if se else 0
            if long_count >= confirm_bars and long_count >= short_count:
                position = 1
                hold_bars = 0
                long_count = 0
                short_count = 0
            elif short_count >= confirm_bars:
                position = -1
                hold_bars = 0
                long_count = 0
                short_count = 0
        elif position == 1:
            hold_bars += 1
            short_count = short_count + 1 if se else 0
            if hold_bars >= min_hold_bars and (xl or short_count >= confirm_bars):
                position = -1 if short_count >= confirm_bars else 0
                hold_bars = 0
                long_count = 0
                short_count = 0
        else:
            hold_bars += 1
            long_count = long_count + 1 if le else 0
            if hold_bars >= min_hold_bars and (xs or long_count >= confirm_bars):
                position = 1 if long_count >= confirm_bars else 0
                hold_bars = 0
                long_count = 0
                short_count = 0

        signal.iloc[i] = position

    return signal


def strategy_trend(df: pd.DataFrame) -> pd.Series:
    """
    Trend following:
    long when the fast/medium EMAs stack bullish above the long EMA with RSI support,
    short when the stack flips bearish.
    """

    trend_strength = (df["EMA_20"] - df["EMA_50"]).abs() / df["Close"]
    min_trend_strength = trend_strength.rolling(100, min_periods=30).median()
    atr_active = df["ATR_Pct"] > df["ATR_Pct"].rolling(120, min_periods=40).median()

    long_entry = (
        (df["EMA_20"] > df["EMA_50"])
        & (df["EMA_50"] > df["EMA_200"])
        & (df["Momentum_10"] > 0)
        & (df["Close"] > df["EMA_20"])
        & df["RSI_14"].between(52, 72)
        & (trend_strength > min_trend_strength)
        & atr_active
    )
    short_entry = (
        (df["EMA_20"] < df["EMA_50"])
        & (df["EMA_50"] < df["EMA_200"])
        & (df["Momentum_10"] < 0)
        & (df["Close"] < df["EMA_20"])
        & df["RSI_14"].between(28, 48)
        & (trend_strength > min_trend_strength)
        & atr_active
    )
    exit_long = (df["EMA_20"] < df["EMA_50"]) | (df["RSI_14"] < 48)
    exit_short = (df["EMA_20"] > df["EMA_50"]) | (df["RSI_14"] > 52)

    signal = _position_signal(
        long_entry,
        short_entry,
        exit_long,
        exit_short,
        confirm_bars=2,
        min_hold_bars=4,
        name="Signal_Trend",
    )
    return _shift_signal(signal)


def strategy_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """
    Mean reversion:
    buy oversold closes below the lower Bollinger band,
    sell overbought closes above the upper band.
    """

    range_regime = (
        ((df["EMA_20"] - df["EMA_50"]).abs() / df["Close"])
        < ((df["EMA_20"] - df["EMA_50"]).abs() / df["Close"]).rolling(100, min_periods=30).median()
    ) & (df["ATR_Pct"] < df["ATR_Pct"].rolling(120, min_periods=40).quantile(0.65))

    long_entry = (
        (df["Close"] < df["BB_Lower"])
        & (df["RSI_14"] < 32)
        & (df["ZScore_20"] < -1.6)
        & range_regime
    )
    short_entry = (
        (df["Close"] > df["BB_Upper"])
        & (df["RSI_14"] > 68)
        & (df["ZScore_20"] > 1.6)
        & range_regime
    )
    exit_long = (df["Close"] >= df["BB_Mid"]) | (df["RSI_14"] >= 50)
    exit_short = (df["Close"] <= df["BB_Mid"]) | (df["RSI_14"] <= 50)

    signal = _position_signal(
        long_entry,
        short_entry,
        exit_long,
        exit_short,
        confirm_bars=1,
        min_hold_bars=2,
        name="Signal_MR",
    )
    return _shift_signal(signal)


def strategy_breakout(df: pd.DataFrame) -> pd.Series:
    """
    Volatility breakout:
    trade fresh Donchian channel breaks only when ATR regime is active.
    """

    atr_filter = df["ATR_Pct"] > df["ATR_Pct"].rolling(80, min_periods=30).quantile(0.6)
    width_filter = df["BB_Width"] > df["BB_Width"].rolling(80, min_periods=30).median()
    momentum_filter = df["Momentum_10"].abs() > df["Momentum_10"].abs().rolling(80, min_periods=30).median()

    long_entry = (
        (df["Close"] >= df["Donchian_High_20"].shift(1))
        & (df["Momentum_10"] > 0)
        & (df["RSI_14"] > 55)
        & atr_filter
        & width_filter
        & momentum_filter
    )
    short_entry = (
        (df["Close"] <= df["Donchian_Low_20"].shift(1))
        & (df["Momentum_10"] < 0)
        & (df["RSI_14"] < 45)
        & atr_filter
        & width_filter
        & momentum_filter
    )
    exit_long = (df["Close"] < df["EMA_20"]) | (df["RSI_14"] < 50)
    exit_short = (df["Close"] > df["EMA_20"]) | (df["RSI_14"] > 50)

    signal = _position_signal(
        long_entry,
        short_entry,
        exit_long,
        exit_short,
        confirm_bars=2,
        min_hold_bars=3,
        name="Signal_BO",
    )
    return _shift_signal(signal)


def signal_summary(signal: pd.Series, strategy_name: str, pair: str) -> None:
    """Print a compact summary for one signal stream."""

    total = len(signal)
    buys = int((signal == 1).sum())
    sells = int((signal == -1).sum())
    flats = int((signal == 0).sum())
    changes = int((signal != signal.shift(1)).sum())

    print(f"  [{strategy_name}] {pair}")
    print(f"    Long signals : {buys:>5} ({buys / total * 100:>5.1f}%)")
    print(f"    Short signals: {sells:>5} ({sells / total * 100:>5.1f}%)")
    print(f"    Flat         : {flats:>5} ({flats / total * 100:>5.1f}%)")
    print(f"    State changes: {changes:>5}")


def generate_signals(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Attach all strategy signals to the pair dataframe."""

    out = df.copy()
    out["Signal_Trend"] = strategy_trend(out)
    out["Signal_MR"] = strategy_mean_reversion(out)
    out["Signal_BO"] = strategy_breakout(out)

    signal_summary(out["Signal_Trend"], "Trend", pair)
    signal_summary(out["Signal_MR"], "Mean Reversion", pair)
    signal_summary(out["Signal_BO"], "Breakout", pair)
    print()
    return out


def main() -> dict[str, pd.DataFrame]:
    """Generate signal files for each configured forex pair."""

    ensure_directories()
    print("=" * 72)
    print("STEP 2 - FOREX SIGNAL GENERATION")
    print("Models: Trend, Mean Reversion, Breakout")
    print("Execution assumption: signals are shifted by one bar")
    print("=" * 72 + "\n")

    all_signals: dict[str, pd.DataFrame] = {}
    for pair in FOREX_PAIRS:
        path = os.path.join(DATA_DIR, f"{pair}.csv")
        if not os.path.exists(path):
            print(f"SKIP - missing {path}. Run Data.py first.\n")
            continue

        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        print(f"Processing {pair} ({len(df)} rows)")
        print("-" * 52)
        signals_df = generate_signals(df, pair)
        signals_df.to_csv(os.path.join(SIGNALS_DIR, f"{pair}_signals.csv"))
        all_signals[pair] = signals_df

    if all_signals:
        sample_pair = next(iter(all_signals))
        sample = all_signals[sample_pair]
        cols = [
            "Close",
            "EMA_20",
            "EMA_50",
            "EMA_200",
            "RSI_14",
            "ATR_14",
            "Signal_Trend",
            "Signal_MR",
            "Signal_BO",
        ]
        print("=" * 72)
        print(f"SIGNAL PREVIEW - {sample_pair}")
        print("=" * 72)
        print(sample[cols].tail(10).to_string())

    print(f"\nSaved signals to .\\{SIGNALS_DIR}\\")
    return all_signals


if __name__ == "__main__":
    main()
