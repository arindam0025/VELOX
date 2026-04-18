"""Shared configuration for the forex backtesting pipeline."""

from __future__ import annotations

import os

INITIAL_CAPITAL = 100_000.0
RISK_FREE_RATE = 0.03
TRADING_DAYS = 252

DATA_DIR = "data"
SIGNALS_DIR = "signals"
PORTFOLIO_DIR = "portfolio"
RESULTS_DIR = "results"

FOREX_PAIRS = {
    "EUR_USD": "EURUSD=X",
    "GBP_USD": "GBPUSD=X",
    "USD_JPY": "JPY=X",
    "AUD_USD": "AUDUSD=X",
    "USD_CHF": "CHF=X",
    "USD_CAD": "CAD=X",
    "NZD_USD": "NZDUSD=X",
    "EUR_JPY": "EURJPY=X",
}

STRATEGIES = ("Trend", "MeanReversion", "Breakout")
SIGNAL_COLUMNS = {
    "Trend": "Signal_Trend",
    "MeanReversion": "Signal_MR",
    "Breakout": "Signal_BO",
}

PAIR_SPREAD_PIPS = {
    "EUR_USD": 1.0,
    "GBP_USD": 1.4,
    "USD_JPY": 1.2,
    "AUD_USD": 1.1,
    "USD_CHF": 1.3,
    "USD_CAD": 1.3,
    "NZD_USD": 1.8,
    "EUR_JPY": 1.8,
}


def ensure_directories() -> None:
    """Create all output directories used by the pipeline."""

    for path in (DATA_DIR, SIGNALS_DIR, PORTFOLIO_DIR, RESULTS_DIR):
        os.makedirs(path, exist_ok=True)


def pip_size(pair: str) -> float:
    """Return the standard pip size for the given forex pair."""

    return 0.01 if pair.endswith("JPY") else 0.0001


def pip_value_per_unit_usd(pair: str, price: float) -> float:
    """
    Approximate USD value of one pip for a single unit.

    This is exact for pairs quoted in USD and a practical approximation for
    JPY / cross pairs so the backtester can remain self-contained.
    """

    size = pip_size(pair)
    if pair.endswith("USD"):
        return size
    return size / max(price, 1e-9)
