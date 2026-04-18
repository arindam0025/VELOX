"""
Forex execution engine.

Runs a single-position directional backtest with:
- spread and slippage on entry/exit
- ATR-based stop loss and take profit
- risk-per-trade sizing
- long and short trades
- mark-to-market portfolio tracking
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

from forex_config import (
    FOREX_PAIRS,
    INITIAL_CAPITAL,
    PAIR_SPREAD_PIPS,
    PORTFOLIO_DIR,
    RESULTS_DIR,
    SIGNALS_DIR,
    SIGNAL_COLUMNS,
    STRATEGIES,
    ensure_directories,
    pip_size,
    pip_value_per_unit_usd,
)

RISK_PER_TRADE_PCT = 0.01
STOP_ATR_MULTIPLE = 1.5
TAKE_PROFIT_R = 2.0
SLIPPAGE_PIPS = 0.2
MIN_STOP_PIPS = 8.0
MAX_GROSS_LEVERAGE = 5.0


@dataclass
class Position:
    """Mutable state for the currently open trade."""

    direction: int
    entry_date: pd.Timestamp
    entry_price: float
    units: float
    stop_price: float
    take_profit_price: float
    risk_amount: float
    spread_cost: float
    slippage_cost: float
    signal_name: str


def pair_spread_price(pair: str) -> float:
    """Convert configured spread from pips to price units."""

    return PAIR_SPREAD_PIPS.get(pair, 1.5) * pip_size(pair)


def trade_slippage_price(pair: str) -> float:
    """Convert slippage from pips to price units."""

    return SLIPPAGE_PIPS * pip_size(pair)


def risk_position_units(pair: str, price: float, atr_value: float, equity: float) -> float:
    """Size the trade so the ATR stop risks roughly 1% of equity."""

    stop_distance = max(atr_value * STOP_ATR_MULTIPLE, pip_size(pair) * MIN_STOP_PIPS)
    pip_value = pip_value_per_unit_usd(pair, price)
    risk_per_unit = (stop_distance / pip_size(pair)) * pip_value
    if risk_per_unit <= 0 or equity <= 0 or price <= 0:
        return 0.0
    risk_based_units = (equity * RISK_PER_TRADE_PCT) / risk_per_unit
    leverage_capped_units = (equity * MAX_GROSS_LEVERAGE) / price
    return max(0.0, min(risk_based_units, leverage_capped_units))


def open_position(
    date: pd.Timestamp,
    row: pd.Series,
    pair: str,
    direction: int,
    equity: float,
    signal_name: str,
) -> Position | None:
    """Create a new position from the next-bar open."""

    if pd.isna(row["ATR_14"]) or row["ATR_14"] <= 0:
        return None

    spread = pair_spread_price(pair)
    slippage = trade_slippage_price(pair)
    price = float(row["Open"])

    if direction == 1:
        entry_price = price + spread / 2 + slippage
    else:
        entry_price = price - spread / 2 - slippage

    units = risk_position_units(pair, entry_price, float(row["ATR_14"]), equity)
    if units <= 0:
        return None

    stop_distance = max(float(row["ATR_14"]) * STOP_ATR_MULTIPLE, pip_size(pair) * MIN_STOP_PIPS)
    if direction == 1:
        stop_price = entry_price - stop_distance
        take_profit_price = entry_price + stop_distance * TAKE_PROFIT_R
    else:
        stop_price = entry_price + stop_distance
        take_profit_price = entry_price - stop_distance * TAKE_PROFIT_R

    return Position(
        direction=direction,
        entry_date=date,
        entry_price=entry_price,
        units=units,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
        risk_amount=equity * RISK_PER_TRADE_PCT,
        spread_cost=(spread / pip_size(pair)) * pip_value_per_unit_usd(pair, entry_price) * units,
        slippage_cost=(slippage / pip_size(pair)) * pip_value_per_unit_usd(pair, entry_price) * units,
        signal_name=signal_name,
    )


def mark_to_market(position: Position | None, close_price: float, equity: float) -> float:
    """Compute end-of-bar portfolio value."""

    if position is None:
        return equity
    unrealized = (close_price - position.entry_price) * position.units * position.direction
    return equity + unrealized


def close_trade(
    position: Position,
    date: pd.Timestamp,
    exit_price: float,
    reason: str,
    equity: float,
) -> tuple[dict[str, object], float]:
    """Close the trade and return the trade record plus realized equity."""

    pnl = (exit_price - position.entry_price) * position.units * position.direction
    realized_equity = max(0.0, equity + pnl)
    trade = {
        "Entry_Date": position.entry_date,
        "Exit_Date": date,
        "Direction": "LONG" if position.direction == 1 else "SHORT",
        "Strategy": position.signal_name,
        "Entry_Price": round(position.entry_price, 6),
        "Exit_Price": round(exit_price, 6),
        "Units": round(position.units, 2),
        "PnL": round(pnl, 2),
        "PnL_Pct": round((pnl / max(equity, 1e-9)) * 100, 2),
        "Hold_Days": (date - position.entry_date).days,
        "Risk_Amount": round(position.risk_amount, 2),
        "Spread_Cost": round(position.spread_cost, 2),
        "Slippage_Cost": round(position.slippage_cost, 2),
        "Exit_Reason": reason,
    }
    return trade, realized_equity


def stop_or_target_hit(position: Position, row: pd.Series, pair: str) -> tuple[bool, float, str]:
    """Check whether stop-loss or target was touched inside the candle."""

    high = float(row["High"])
    low = float(row["Low"])
    spread = pair_spread_price(pair)
    slippage = trade_slippage_price(pair)

    if position.direction == 1:
        if low <= position.stop_price:
            return True, position.stop_price - spread / 2 - slippage, "Stop"
        if high >= position.take_profit_price:
            return True, position.take_profit_price - spread / 2 - slippage, "Target"
    else:
        if high >= position.stop_price:
            return True, position.stop_price + spread / 2 + slippage, "Stop"
        if low <= position.take_profit_price:
            return True, position.take_profit_price + spread / 2 + slippage, "Target"
    return False, 0.0, ""


def exit_on_signal(position: Position, row: pd.Series, pair: str) -> float:
    """Exit a still-open trade using the bar open when direction flips."""

    spread = pair_spread_price(pair)
    slippage = trade_slippage_price(pair)
    price = float(row["Open"])
    if position.direction == 1:
        return price - spread / 2 - slippage
    return price + spread / 2 + slippage


def run_backtest(df: pd.DataFrame, pair: str, signal_col: str, strategy_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the bar-by-bar backtest for one pair and one strategy."""

    equity = INITIAL_CAPITAL
    position: Position | None = None
    portfolio_rows: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []

    for date, row in df.iterrows():
        signal = int(row.get(signal_col, 0))
        action = "HOLD"

        if position is not None:
            hit, exit_price, reason = stop_or_target_hit(position, row, pair)
            if hit:
                trade, equity = close_trade(position, date, exit_price, reason, equity)
                trades.append(trade)
                position = None
                action = reason.upper()

        if position is not None and signal != 0 and signal != position.direction:
            exit_price = exit_on_signal(position, row, pair)
            trade, equity = close_trade(position, date, exit_price, "SignalFlip", equity)
            trades.append(trade)
            position = None
            action = "REVERSE"

        if position is None and signal != 0 and equity > 0:
            position = open_position(date, row, pair, signal, equity, strategy_name)
            if position is not None:
                action = "BUY" if signal == 1 else "SELL"

        close_price = float(row["Close"])
        portfolio_value = mark_to_market(position, close_price, equity)
        portfolio_rows.append(
            {
                "Date": date,
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": close_price,
                "Signal": signal,
                "Position": 0 if position is None else position.direction,
                "Units": 0.0 if position is None else round(position.units, 2),
                "Cash_Equity": round(equity, 2),
                "Portfolio_Value": round(portfolio_value, 2),
                "Stop_Price": None if position is None else round(position.stop_price, 6),
                "Take_Profit": None if position is None else round(position.take_profit_price, 6),
                "Action": action,
            }
        )

    if position is not None:
        final_close = float(df["Close"].iloc[-1])
        exit_price = final_close - pair_spread_price(pair) / 2 if position.direction == 1 else final_close + pair_spread_price(pair) / 2
        trade, equity = close_trade(position, df.index[-1], exit_price, "EndOfTest", equity)
        trades.append(trade)
        portfolio_rows[-1]["Portfolio_Value"] = round(equity, 2)
        portfolio_rows[-1]["Action"] = "FORCED_EXIT"

    portfolio_df = pd.DataFrame(portfolio_rows).set_index("Date")
    trades_df = pd.DataFrame(trades)
    return portfolio_df, trades_df


def trade_summary(trades_df: pd.DataFrame) -> dict[str, float]:
    """Summarize trade-level outputs for console logging."""

    if trades_df.empty:
        return {"trades": 0, "win_rate": 0.0, "pnl": 0.0}
    return {
        "trades": float(len(trades_df)),
        "win_rate": float((trades_df["PnL"] > 0).mean() * 100),
        "pnl": float(trades_df["PnL"].sum()),
    }


def main() -> dict[str, dict[str, pd.DataFrame]]:
    """Execute all strategy backtests for all configured forex pairs."""

    ensure_directories()
    print("=" * 72)
    print("STEP 3 - FOREX EXECUTION ENGINE")
    print(f"Initial Capital : ${INITIAL_CAPITAL:,.2f}")
    print(f"Risk / Trade    : {RISK_PER_TRADE_PCT * 100:.1f}%")
    print(f"Stop Model      : {STOP_ATR_MULTIPLE:.1f} x ATR")
    print(f"Reward Target   : {TAKE_PROFIT_R:.1f}R")
    print("=" * 72 + "\n")

    all_results: dict[str, dict[str, pd.DataFrame]] = {}
    summary_rows: list[dict[str, object]] = []

    for pair in FOREX_PAIRS:
        path = os.path.join(SIGNALS_DIR, f"{pair}_signals.csv")
        if not os.path.exists(path):
            print(f"SKIP - missing {path}. Run Strategy.py first.\n")
            continue

        df = pd.read_csv(path, index_col="Date", parse_dates=True)
        all_results[pair] = {}
        print(f"{'=' * 72}\nPair: {pair} | Rows: {len(df)}\n{'=' * 72}")

        for strategy_name in STRATEGIES:
            signal_col = SIGNAL_COLUMNS[strategy_name]
            if signal_col not in df.columns:
                continue

            portfolio_df, trades_df = run_backtest(df, pair, signal_col, strategy_name)
            portfolio_df.to_csv(os.path.join(PORTFOLIO_DIR, f"{pair}_{strategy_name}_portfolio.csv"))
            trades_df.to_csv(os.path.join(PORTFOLIO_DIR, f"{pair}_{strategy_name}_trades.csv"), index=False)
            all_results[pair][strategy_name] = portfolio_df

            final_value = float(portfolio_df["Portfolio_Value"].iloc[-1])
            total_return = (final_value / INITIAL_CAPITAL - 1) * 100
            summary = trade_summary(trades_df)
            print(
                f"  [{strategy_name:<14}] Final: ${final_value:>11,.2f} "
                f"Return: {total_return:>+7.2f}% "
                f"Trades: {int(summary['trades']):>3} "
                f"Win rate: {summary['win_rate']:>5.1f}%"
            )
            summary_rows.append(
                {
                    "Pair": pair,
                    "Strategy": strategy_name,
                    "Final_Value": round(final_value, 2),
                    "Total_Return": round(total_return, 2),
                    "Trades": int(summary["trades"]),
                    "Win_Rate": round(summary["win_rate"], 1),
                    "Net_PnL": round(summary["pnl"], 2),
                }
            )
        print()

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(os.path.join(RESULTS_DIR, "execution_summary.csv"), index=False)
        print(f"Saved portfolio curves and trade logs to .\\{PORTFOLIO_DIR}\\")
        print(f"Saved execution summary to .\\{RESULTS_DIR}\\execution_summary.csv")

    return all_results


if __name__ == "__main__":
    main()
