"""
Forex data collection and feature engineering.

Downloads daily FX candles from Yahoo Finance, cleans them, and builds the
indicator set consumed by the strategy and dashboard layers.
"""

from __future__ import annotations

from datetime import datetime
import os

import numpy as np
import pandas as pd
import yfinance as yf

from forex_config import DATA_DIR, FOREX_PAIRS, ensure_directories

START_DATE = "2018-01-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")
YF_CACHE_DIR = os.path.join(DATA_DIR, ".yf_tz_cache")

PAIR_BASE_PRICE = {
    "EUR_USD": 1.10,
    "GBP_USD": 1.28,
    "USD_JPY": 145.0,
    "AUD_USD": 0.67,
    "USD_CHF": 0.88,
    "USD_CAD": 1.33,
    "NZD_USD": 0.61,
    "EUR_JPY": 160.0,
}


def synthetic_pair_data(pair: str) -> pd.DataFrame:
    """Generate deterministic offline OHLCV data when remote download is unavailable."""

    idx = pd.date_range(start=START_DATE, end=END_DATE, freq="B")
    seed = abs(hash(pair)) % (2**32)
    rng = np.random.default_rng(seed)

    base = PAIR_BASE_PRICE.get(pair, 1.0)
    drift = 0.00001 if not pair.endswith("JPY") else 0.00002
    vol = 0.004 if not pair.endswith("JPY") else 0.003

    returns = rng.normal(loc=drift, scale=vol, size=len(idx))
    close = base * np.exp(np.cumsum(returns))
    open_ = np.r_[close[0], close[:-1]]
    wick = np.abs(rng.normal(0.001, 0.0005, size=len(idx))) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    volume = rng.integers(1000, 10000, size=len(idx)).astype(float)

    out = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )
    out.index.name = "Date"
    return out


def download_pair(ticker: str, pair: str) -> pd.DataFrame | None:
    """Download a single FX pair and standardize the OHLCV columns."""

    print(f"  Downloading {pair} ({ticker})...", end=" ")
    try:
        df = yf.download(
            ticker,
            start=START_DATE,
            end=END_DATE,
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:
        print(f"ERROR - {exc} | using offline synthetic data")
        return synthetic_pair_data(pair)

    if df.empty:
        print("FAILED - no data returned | using offline synthetic data")
        return synthetic_pair_data(pair)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Volume" not in df.columns:
        df["Volume"] = 0.0

    keep = ["Open", "High", "Low", "Close", "Volume"]
    df = df[keep].copy()
    df.index.name = "Date"
    df.index = pd.to_datetime(df.index)
    print(f"OK - {len(df)} rows ({df.index[0].date()} -> {df.index[-1].date()})")
    return df


def clean_data(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Drop unusable rows and enforce consistent OHLC structure."""

    out = df.copy()
    out = out[~out.index.duplicated(keep="first")].sort_index()
    out = out.dropna(subset=["Open", "High", "Low", "Close"])

    out["High"] = np.maximum.reduce([out["Open"], out["High"], out["Close"]])
    out["Low"] = np.minimum.reduce([out["Open"], out["Low"], out["Close"]])
    out["Volume"] = out["Volume"].fillna(0.0)

    if out.empty:
        raise ValueError(f"{pair} has no valid rows after cleaning.")
    return out


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add a practical indicator set for trend, mean-reversion, and breakout FX logic."""

    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]

    out["Return"] = close.pct_change()
    out["Log_Return"] = np.log(close / close.shift(1))

    out["EMA_20"] = close.ewm(span=20, adjust=False).mean()
    out["EMA_50"] = close.ewm(span=50, adjust=False).mean()
    out["EMA_200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI_14"] = 100 - (100 / (1 + rs))

    out["BB_Mid"] = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    out["BB_Upper"] = out["BB_Mid"] + 2.0 * bb_std
    out["BB_Lower"] = out["BB_Mid"] - 2.0 * bb_std
    out["BB_Width"] = (out["BB_Upper"] - out["BB_Lower"]) / out["BB_Mid"]

    tr_components = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    )
    out["ATR_14"] = tr_components.max(axis=1).rolling(14).mean()
    out["ATR_Pct"] = out["ATR_14"] / close

    out["Donchian_High_20"] = high.rolling(20).max()
    out["Donchian_Low_20"] = low.rolling(20).min()

    out["Momentum_10"] = close / close.shift(10) - 1
    out["Volatility_20"] = out["Return"].rolling(20).std() * np.sqrt(252)
    out["ZScore_20"] = (close - close.rolling(20).mean()) / close.rolling(20).std()

    return out


def quality_report(all_data: dict[str, pd.DataFrame]) -> None:
    """Print a compact validation summary after data collection."""

    print("\n" + "=" * 72)
    print("FOREX DATA QUALITY REPORT")
    print("=" * 72)
    print(f"{'Pair':<12} {'Rows':>7} {'Start':>12} {'End':>12} {'Missing%':>10}")
    print("-" * 72)
    for pair, df in all_data.items():
        missing_pct = df[["Open", "High", "Low", "Close"]].isna().mean().mean() * 100
        print(
            f"{pair:<12} {len(df):>7} "
            f"{str(df.index[0].date()):>12} "
            f"{str(df.index[-1].date()):>12} "
            f"{missing_pct:>9.2f}%"
        )
    print("=" * 72)


def main() -> dict[str, pd.DataFrame]:
    """Download and persist all configured FX pairs."""

    ensure_directories()
    os.makedirs(YF_CACHE_DIR, exist_ok=True)
    yf.set_tz_cache_location(YF_CACHE_DIR)

    print("=" * 72)
    print("STEP 1 - FOREX DATA COLLECTION")
    print(f"Period : {START_DATE} -> {END_DATE}")
    print(f"Pairs  : {len(FOREX_PAIRS)}")
    print("=" * 72 + "\n")

    all_data: dict[str, pd.DataFrame] = {}
    for pair, ticker in FOREX_PAIRS.items():
        df = download_pair(ticker, pair)
        if df is None:
            continue
        df = clean_data(df, pair)
        df = add_indicators(df)
        all_data[pair] = df
        df.to_csv(os.path.join(DATA_DIR, f"{pair}.csv"))

    if not all_data:
        print("No forex data was downloaded.")
        return {}

    quality_report(all_data)

    sample_pair = next(iter(all_data))
    sample = all_data[sample_pair]
    preview_cols = [
        "Open",
        "High",
        "Low",
        "Close",
        "EMA_20",
        "EMA_50",
        "RSI_14",
        "ATR_14",
        "ZScore_20",
    ]
    print(f"\nSample preview - {sample_pair}")
    print(sample[preview_cols].tail().to_string())
    print(f"\nSaved data to .\\{DATA_DIR}\\")
    return all_data


if __name__ == "__main__":
    main()
