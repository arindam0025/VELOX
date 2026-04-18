# Forex Live Backtest Lab

A forex research and execution simulation project with:

- Multi-strategy signal generation (`Trend`, `MeanReversion`, `Breakout`)
- Realistic backtest engine (spread, slippage, ATR stops, risk-based sizing)
- Metrics pipeline (returns, Sharpe, drawdown, win rate, profit factor)
- Streamlit dashboard with:
  - Backtest analytics
  - Live monitoring mode
  - Timeline filters
  - Executed long/short markers
  - Volume + order flow panel

## Project Structure

```text
Data.py           # Step 1: Data collection + indicators
Strategy.py       # Step 2: Signal generation
Engine.py         # Step 3: Backtest execution
metric.py         # Step 4: Performance reporting
dashboard.py      # Streamlit UI (backtest + live)
forex_config.py   # Shared config/constants

data/             # Input OHLCV and engineered features
signals/          # Generated signal files
portfolio/        # Portfolio curves + trade logs
results/          # Summaries/metrics exports
tests/            # Unit tests
```

## Features

### Backtesting

- Pair-level strategy runs across configured forex instruments
- Transaction realism:
  - spread model (pair-specific)
  - slippage
  - ATR stop and R-multiple target
  - risk-per-trade position sizing
- Trade logs include direction, entry/exit, PnL, hold duration, exit reason

### Dashboard

- Live mode with auto-refresh
- Chart interval controls (`1m` to `1D`)
- Timeline range filters for historical analysis
- Strategy selection and side-by-side metrics
- Executed marker overlays:
  - Long Entry / Short Entry
  - Long Exit / Short Exit
- Order flow and volume panel:
  - Volume bars
  - CVD (Cumulative Volume Delta)
  - OFI (Order Flow Imbalance)

### Data Sources

- Yahoo Finance intraday/daily feed fallback
- OANDA quote polling (when credentials are configured)
- Offline-safe synthetic fallback in restricted network scenarios

## Quick Start

### 1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install pandas numpy yfinance streamlit plotly requests pytest
```

### 3) Run full pipeline

```powershell
.\.venv\Scripts\python.exe Data.py
.\.venv\Scripts\python.exe Strategy.py
.\.venv\Scripts\python.exe Engine.py
.\.venv\Scripts\python.exe metric.py
```

### 4) Launch dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open: `http://localhost:8501`

## Live Mode (Optional OANDA)

Set environment variables to use OANDA in live mode:

```powershell
$env:OANDA_API_TOKEN="your_token"
$env:OANDA_ACCOUNT_ID="your_account_id"
$env:OANDA_ENVIRONMENT="practice"   # or "live"
```

If OANDA is not configured, the dashboard uses Yahoo feed fallback.

## Tests

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Outputs

- `signals/*_signals.csv`
- `portfolio/*_portfolio.csv`
- `portfolio/*_trades.csv`
- `results/execution_summary.csv`
- `results/forex_metrics_summary.csv`

## Troubleshooting

### Streamlit duplicate chart ID

If you saw `StreamlitDuplicateElementId` before, this repo now uses explicit keys for all Plotly charts.

### No volume in forex feed

Some forex sources return zero volume. The dashboard computes `Volume_Effective` proxy values so order flow visuals still work.

### “This site can’t be reached”

Make sure Streamlit is running in an active terminal session:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

## Notes

- This is a research/backtesting tool, not financial advice.
- Strategy behavior depends heavily on data source quality and timeframe.
- For production trading, add broker-grade validation, risk limits, and monitoring.
