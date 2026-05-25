# VELOX

> **Multi-strategy forex research & execution simulation system.**
> Signal generation → realistic backtesting → performance analytics → live dashboard.

---

## What is VELOX?

VELOX is a modular forex research pipeline built entirely in Python. It downloads real market data, generates directional signals using three independent strategies, simulates realistic trade execution with broker-grade costs, and presents everything through an interactive Streamlit dashboard with live monitoring support.

It is designed to answer one question with precision: **does this strategy actually work, and by how much?**

---

## Pipeline Overview

VELOX runs as a sequential pipeline. Each module does one job.

```
Data.py       →   Strategy.py   →   Engine.py   →   metric.py   →   dashboard.py
  │                   │                │                │                │
Fetch OHLCV       Generate          Simulate         Calculate        Visualise
+ indicators      signals           trades           performance      everything
```

---

## Strategies

Three independent strategies run in parallel. Each produces a signal: `+1` (long), `-1` (short), or `0` (flat).

| Strategy | Logic | Entry Condition |
|---|---|---|
| **Trend** | EMA crossover + RSI filter | Fast EMA crosses above slow EMA, RSI in healthy zone |
| **Mean Reversion** | Bollinger Bands + RSI | Price below lower band, RSI oversold < 32 |
| **Breakout** | Donchian Channel | Price breaks above N-period highest high |

Signals are saved to `signals/` and consumed by the backtest engine independently.

---

## Backtest Engine

The engine simulates trades bar by bar with full transaction realism — not idealised fills.

**What gets modelled:**

- Spread cost per pair (pair-specific, not flat)
- Slippage on entry and exit
- ATR-based stop loss — wider in volatile markets, tighter when calm
- Take profit at 2× the stop distance (minimum 1:2 risk/reward enforced)
- Risk-per-trade position sizing — lot size calculated so every trade risks the same fixed % of capital regardless of pair or stop distance
- Mark-to-market portfolio curve updated every bar

**Every trade log records:** direction, entry price, exit price, entry time, exit time, hold duration, P&L, exit reason (stop / target / signal flip).

---

## Performance Metrics

`metric.py` calculates the full performance report from trade logs:

| Metric | Description |
|---|---|
| Total Return | Overall portfolio growth % |
| Sharpe Ratio | Return per unit of risk. Target > 1.0 |
| Max Drawdown | Worst peak-to-trough loss |
| Win Rate | % of trades that were profitable |
| Profit Factor | Gross profit / gross loss. Target > 1.3 |
| Avg Hold Duration | Mean bars per trade |

Results saved to `results/forex_metrics_summary.csv` and `results/execution_summary.csv`.

---

## Dashboard

```bash
streamlit run dashboard.py
# → http://localhost:8501
```

**Backtest mode:**

- Price chart with long/short entry and exit markers overlaid
- Portfolio equity curve per strategy
- Strategy selector and side-by-side metrics comparison
- Timeline range filters for historical analysis
- Interval controls from `1m` to `1D`

**Live mode:**

- Auto-refresh feed via Yahoo Finance (default) or OANDA (optional)
- Real-time price chart
- Volume bars + CVD (Cumulative Volume Delta) + OFI (Order Flow Imbalance) panel

> CVD and OFI are advanced order flow indicators. CVD tracks whether buyers or sellers are more aggressive over time. OFI measures the imbalance between buy and sell pressure at the microstructure level.

---

## Project Structure

```
velox/
├── Data.py                        # Step 1 — OHLCV download + indicator calculation
├── Strategy.py                    # Step 2 — Signal generation (Trend, MeanRev, Breakout)
├── Engine.py                      # Step 3 — Backtest execution engine
├── metric.py                      # Step 4 — Performance metrics pipeline
├── dashboard.py                   # Step 5 — Streamlit UI (backtest + live)
├── forex_config.py                # Shared config, pairs, parameters
├── data/                          # Raw OHLCV + engineered feature files
├── signals/                       # Generated signal CSVs per pair/strategy
├── portfolio/                     # Equity curves + full trade logs
├── results/                       # Metrics summaries
└── tests/                         # Unit tests (pytest)
```

---

## Quick Start

**1. Create virtual environment**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**2. Install dependencies**

```powershell
pip install pandas numpy yfinance streamlit plotly requests pytest
```

**3. Run the full pipeline**

```powershell
.\.venv\Scripts\python.exe Data.py
.\.venv\Scripts\python.exe Strategy.py
.\.venv\Scripts\python.exe Engine.py
.\.venv\Scripts\python.exe metric.py
```

**4. Launch dashboard**

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

---

## Live Mode — OANDA (Optional)

By default VELOX uses Yahoo Finance as its data feed. To switch to OANDA live quotes:

```powershell
$env:OANDA_API_TOKEN="your_token"
$env:OANDA_ACCOUNT_ID="your_account_id"
$env:OANDA_ENVIRONMENT="practice"    # or "live"
```

If OANDA credentials are not set, the dashboard falls back to Yahoo Finance automatically. No config change needed.

---

## Outputs

| File | Contents |
|---|---|
| `signals/*_signals.csv` | Buy/sell/flat signals per pair and strategy |
| `portfolio/*_portfolio.csv` | Portfolio equity curve bar by bar |
| `portfolio/*_trades.csv` | Full trade log with entry, exit, P&L, duration |
| `results/execution_summary.csv` | Strategy × pair summary table |
| `results/forex_metrics_summary.csv` | Sharpe, drawdown, win rate, profit factor |

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

## Troubleshooting

**`StreamlitDuplicateElementId` error**
All Plotly charts now use explicit keys. This error should not appear in the current version.

**Zero volume in forex feed**
Some forex data sources return zero volume. VELOX computes a `Volume_Effective` proxy so the CVD and OFI panels always render correctly.

**Dashboard not loading**
Streamlit must be running in an active terminal. Do not close the terminal after launching.

---

## Disclaimer

VELOX is a research and backtesting tool. It does not constitute financial advice. Backtested results do not guarantee future performance. For live trading, add broker-grade validation, proper risk controls, and regulatory compliance.

---

*Built with Python · pandas · NumPy · yfinance · Streamlit · Plotly · OANDA API*
