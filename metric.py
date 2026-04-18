"""Performance metrics for the forex backtesting pipeline."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError

from forex_config import PORTFOLIO_DIR, RESULTS_DIR, RISK_FREE_RATE, STRATEGIES, TRADING_DAYS, ensure_directories


def total_return(values: pd.Series) -> float:
    return (values.iloc[-1] / values.iloc[0] - 1) * 100


def annual_return(values: pd.Series) -> float:
    periods = len(values)
    if periods <= 1:
        return 0.0
    start = float(values.iloc[0])
    end = float(values.iloc[-1])
    if start <= 0:
        return 0.0
    if end <= 0:
        return -100.0
    return ((end / start) ** (TRADING_DAYS / periods) - 1) * 100


def annualized_volatility(values: pd.Series) -> float:
    returns = values.pct_change().dropna()
    if returns.empty:
        return 0.0
    return returns.std() * np.sqrt(TRADING_DAYS) * 100


def max_drawdown(values: pd.Series) -> float:
    drawdowns = values / values.cummax() - 1
    return drawdowns.min() * 100


def sharpe_ratio(values: pd.Series) -> float:
    returns = values.pct_change().dropna()
    if returns.empty or returns.std() == 0:
        return 0.0
    excess = returns - (RISK_FREE_RATE / TRADING_DAYS)
    return (excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS)


def sortino_ratio(values: pd.Series) -> float:
    returns = values.pct_change().dropna()
    if returns.empty:
        return 0.0
    excess = returns - (RISK_FREE_RATE / TRADING_DAYS)
    downside = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return ((annual_return(values) / 100) - RISK_FREE_RATE) / (downside.std() * np.sqrt(TRADING_DAYS))


def calmar_ratio(values: pd.Series) -> float:
    mdd = abs(max_drawdown(values))
    if mdd == 0:
        return 0.0
    return (annual_return(values) / 100) / (mdd / 100)


def exposure_pct(portfolio_df: pd.DataFrame) -> float:
    if "Position" not in portfolio_df.columns:
        return 0.0
    return (portfolio_df["Position"] != 0).mean() * 100


def win_rate(trades_df: pd.DataFrame) -> float:
    if trades_df.empty or "PnL" not in trades_df.columns:
        return 0.0
    return (trades_df["PnL"] > 0).mean() * 100


def profit_factor(trades_df: pd.DataFrame) -> float:
    if trades_df.empty or "PnL" not in trades_df.columns:
        return 0.0
    gross_profit = trades_df.loc[trades_df["PnL"] > 0, "PnL"].sum()
    gross_loss = abs(trades_df.loc[trades_df["PnL"] < 0, "PnL"].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def expectancy(trades_df: pd.DataFrame) -> float:
    if trades_df.empty or "PnL" not in trades_df.columns:
        return 0.0
    return float(trades_df["PnL"].mean())


def avg_hold_days(trades_df: pd.DataFrame) -> float:
    if trades_df.empty or "Hold_Days" not in trades_df.columns:
        return 0.0
    return float(trades_df["Hold_Days"].mean())


def compute_metrics(portfolio_df: pd.DataFrame, trades_df: pd.DataFrame, pair: str, strategy: str) -> dict[str, object]:
    values = portfolio_df["Portfolio_Value"]
    return {
        "Pair": pair,
        "Strategy": strategy,
        "Total_Return": round(total_return(values), 2),
        "Annual_Return": round(annual_return(values), 2),
        "Volatility": round(annualized_volatility(values), 2),
        "Max_Drawdown": round(max_drawdown(values), 2),
        "Sharpe_Ratio": round(sharpe_ratio(values), 3),
        "Sortino_Ratio": round(sortino_ratio(values), 3),
        "Calmar_Ratio": round(calmar_ratio(values), 3),
        "Exposure_Pct": round(exposure_pct(portfolio_df), 1),
        "Win_Rate": round(win_rate(trades_df), 1),
        "Profit_Factor": round(profit_factor(trades_df), 2),
        "Expectancy": round(expectancy(trades_df), 2),
        "Num_Trades": int(len(trades_df)),
        "Avg_Hold_Days": round(avg_hold_days(trades_df), 1),
        "Final_Value": round(float(values.iloc[-1]), 2),
    }


def portfolio_files() -> list[Path]:
    root = Path(PORTFOLIO_DIR)
    files: list[Path] = []
    for path in root.glob("*_portfolio.csv"):
        name = path.name
        if any(name.endswith(f"_{strategy}_portfolio.csv") for strategy in STRATEGIES):
            files.append(path)
    return sorted(files)


def pair_and_strategy_from_file(path: Path) -> tuple[str, str]:
    name = path.name
    for strategy in STRATEGIES:
        suffix = f"_{strategy}_portfolio.csv"
        if name.endswith(suffix):
            pair = name[: -len(suffix)]
            return pair, strategy
    raise ValueError(f"Unrecognized portfolio filename format: {name}")


def main() -> pd.DataFrame:
    ensure_directories()
    rows: list[dict[str, object]] = []
    files = portfolio_files()

    if not files:
        print("No portfolio files found. Run Engine.py first.")
        return pd.DataFrame()

    print("=" * 72)
    print("STEP 4 - FOREX PERFORMANCE METRICS")
    print("=" * 72)

    for portfolio_path in files:
        pair, strategy = pair_and_strategy_from_file(portfolio_path)
        trades_path = Path(PORTFOLIO_DIR) / f"{pair}_{strategy}_trades.csv"

        try:
            portfolio_df = pd.read_csv(portfolio_path, index_col="Date", parse_dates=True)
        except EmptyDataError:
            print(f"SKIP {portfolio_path.name} - empty file")
            continue
        if portfolio_df.empty:
            print(f"SKIP {portfolio_path.name} - no rows")
            continue

        try:
            trades_df = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
        except EmptyDataError:
            trades_df = pd.DataFrame()
        metrics = compute_metrics(portfolio_df, trades_df, pair, strategy)
        rows.append(metrics)

        print(
            f"{pair:<10} {strategy:<14} "
            f"Return {metrics['Total_Return']:>7.2f}% | "
            f"Sharpe {metrics['Sharpe_Ratio']:>5.2f} | "
            f"MaxDD {metrics['Max_Drawdown']:>7.2f}% | "
            f"Trades {metrics['Num_Trades']:>3}"
        )

    summary = pd.DataFrame(rows).sort_values(["Pair", "Sharpe_Ratio", "Total_Return"], ascending=[True, False, False])
    summary.to_csv(os.path.join(RESULTS_DIR, "forex_metrics_summary.csv"), index=False)
    print(f"\nSaved metrics summary to .\\{RESULTS_DIR}\\forex_metrics_summary.csv")
    return summary


if __name__ == "__main__":
    main()
