"""Forex backtesting and live monitoring dashboard."""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from forex_config import FOREX_PAIRS, INITIAL_CAPITAL, PORTFOLIO_DIR, SIGNALS_DIR, STRATEGIES

st.set_page_config(page_title="Forex Live + Backtest Dashboard", page_icon="FX", layout="wide")

LIVE_REFRESH_SECONDS = 1
LIVE_HISTORY_BARS = 240
SUPPORTED_CHART_INTERVALS = ("1m", "5m", "15m", "30m", "1h", "1D")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
    .stApp { background:
        radial-gradient(circle at top left, rgba(44, 146, 164, 0.28), transparent 30%),
        radial-gradient(circle at top right, rgba(255, 129, 82, 0.17), transparent 26%),
        linear-gradient(180deg, #08131a 0%, #0d1e28 100%); }
    section[data-testid="stSidebar"] { background-color:#0a1821; border-right:1px solid #173342; }
    .metric-card { background:rgba(9, 23, 31, 0.88); border:1px solid #244a5a; border-radius:18px; padding:14px; }
    .metric-label { color:#81aab8; font-size:11px; text-transform:uppercase; letter-spacing:1.5px; }
    .metric-value { font-family:'JetBrains Mono', monospace; color:#edf7fb; font-size:26px; font-weight:600; }
    .section-title { color:#73d2de; font-size:12px; text-transform:uppercase; letter-spacing:2px; margin:10px 0; }
    h1, h2, h3 { color:#edf7fb !important; }
    p, label, .stMarkdown, .stCaption { color:#b5c9d3 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

COLORS = {
    "Trend": "#73d2de",
    "MeanReversion": "#f4a261",
    "Breakout": "#e76f51",
}


def section(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def discover_pairs() -> list[str]:
    root = Path(PORTFOLIO_DIR)
    pairs = set()
    for path in root.glob("*_portfolio.csv"):
        name = path.name
        for strategy in STRATEGIES:
            suffix = f"_{strategy}_portfolio.csv"
            if name.endswith(suffix):
                pairs.add(name[: -len(suffix)])
                break
    if pairs:
        return sorted(pairs)
    return sorted(FOREX_PAIRS.keys())


@st.cache_data
def load_portfolio(pair: str, strategy: str) -> pd.DataFrame | None:
    path = Path(PORTFOLIO_DIR) / f"{pair}_{strategy}_portfolio.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, index_col="Date", parse_dates=True)


@st.cache_data
def load_trades(pair: str, strategy: str) -> pd.DataFrame:
    path = Path(PORTFOLIO_DIR) / f"{pair}_{strategy}_trades.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["Entry_Date", "Exit_Date"])


@st.cache_data
def load_signal_frame(pair: str) -> pd.DataFrame | None:
    path = Path(SIGNALS_DIR) / f"{pair}_signals.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, index_col="Date", parse_dates=True)


def calc_metrics(portfolio_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict[str, float]:
    if portfolio_df.empty or len(portfolio_df) < 2:
        return {
            "total": 0.0,
            "annual": 0.0,
            "vol": 0.0,
            "mdd": 0.0,
            "sharpe": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "final": 0.0,
            "trades": float(len(trades_df)),
        }

    pv = portfolio_df["Portfolio_Value"]
    returns = pv.pct_change().dropna()
    total = (pv.iloc[-1] / pv.iloc[0] - 1) * 100
    annual = ((pv.iloc[-1] / pv.iloc[0]) ** (252 / max(len(pv), 1)) - 1) * 100 if len(pv) > 1 else 0.0
    vol = returns.std() * np.sqrt(252) * 100 if not returns.empty else 0.0
    drawdown = (pv / pv.cummax() - 1) * 100
    mdd = drawdown.min()
    sharpe = 0.0
    if not returns.empty and returns.std() > 0:
        sharpe = ((returns - 0.03 / 252).mean() / returns.std()) * np.sqrt(252)
    win_rate = (trades_df["PnL"] > 0).mean() * 100 if not trades_df.empty else 0.0
    profit_factor = 0.0
    if not trades_df.empty:
        gp = trades_df.loc[trades_df["PnL"] > 0, "PnL"].sum()
        gl = abs(trades_df.loc[trades_df["PnL"] < 0, "PnL"].sum())
        profit_factor = gp / gl if gl > 0 else 0.0
    return {
        "total": total,
        "annual": annual,
        "vol": vol,
        "mdd": mdd,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "final": float(pv.iloc[-1]),
        "trades": float(len(trades_df)),
    }


def apply_date_filter_indexed(df: pd.DataFrame | None, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    return df.loc[(df.index >= start_date) & (df.index <= end_date)].copy()


def apply_date_filter_trades(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    if df.empty or "Exit_Date" not in df.columns:
        return df
    return df.loc[(df["Exit_Date"] >= start_date) & (df["Exit_Date"] <= end_date)].copy()


def add_intraday_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA_20"] = out["Close"].ewm(span=20, adjust=False).mean()
    out["EMA_50"] = out["Close"].ewm(span=50, adjust=False).mean()
    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI_14"] = 100 - (100 / (1 + rs))

    out["BB_Mid"] = out["Close"].rolling(20).mean()
    bb_std = out["Close"].rolling(20).std()
    out["BB_Upper"] = out["BB_Mid"] + 2.0 * bb_std
    out["BB_Lower"] = out["BB_Mid"] - 2.0 * bb_std

    out["Donchian_High_20"] = out["High"].rolling(20).max()
    out["Donchian_Low_20"] = out["Low"].rolling(20).min()
    out["Momentum_10"] = out["Close"] / out["Close"].shift(10) - 1

    tr = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - out["Close"].shift(1)).abs(),
            (out["Low"] - out["Close"].shift(1)).abs(),
        ],
        axis=1,
    )
    out["ATR_14"] = tr.max(axis=1).rolling(14).mean()
    out["ATR_Pct"] = out["ATR_14"] / out["Close"]
    raw_vol = out["Volume"].fillna(0.0).astype(float)
    vol_nonzero_ratio = float((raw_vol > 0).mean()) if len(raw_vol) else 0.0
    if vol_nonzero_ratio < 0.1:
        # Forex feeds frequently report zero real volume. Build a stable proxy.
        body = (out["Close"] - out["Open"]).abs() / out["Close"].replace(0, np.nan)
        range_norm = (out["High"] - out["Low"]) / out["Close"].replace(0, np.nan)
        proxy = (body.fillna(0.0) * 2.0 + range_norm.fillna(0.0)) * 1_000_000
        out["Volume_Effective"] = proxy.clip(lower=1_000.0)
        out["Volume_Source"] = "proxy"
    else:
        out["Volume_Effective"] = raw_vol
        out["Volume_Source"] = "feed"

    out["VWAP"] = (out["Close"] * out["Volume_Effective"]).cumsum() / out["Volume_Effective"].cumsum().replace(0, np.nan)
    out["VWAP"] = out["VWAP"].ffill()

    signed_volume = np.sign(out["Close"].diff().fillna(0.0)) * out["Volume_Effective"].fillna(0.0)
    out["Signed_Volume"] = signed_volume
    out["CVD"] = signed_volume.cumsum()
    out["Order_Flow_Imbalance"] = np.sign(out["Close"] - out["Open"]) * out["Volume_Effective"].fillna(0.0)
    return out


def _normalize_time_index(df: pd.DataFrame) -> pd.DataFrame:
    """Drop timezone info for cleaner chart labels and stable plotting."""

    if df.empty:
        return df
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    out.index = idx
    return out


def fetch_live_from_oanda(pair: str) -> tuple[float | None, float | None, str]:
    token = os.getenv("OANDA_API_TOKEN", "").strip()
    account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip()
    env = os.getenv("OANDA_ENVIRONMENT", "practice").strip().lower()
    if not token or not account_id:
        return None, None, "OANDA credentials missing"

    base = "https://api-fxpractice.oanda.com"
    if env == "live":
        base = "https://api-fxtrade.oanda.com"

    instrument = pair.replace("_", "_")
    url = f"{base}/v3/accounts/{account_id}/pricing"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"instruments": instrument},
            timeout=4,
        )
        if resp.status_code >= 400:
            return None, None, f"OANDA HTTP {resp.status_code}"
        payload = resp.json()
        prices = payload.get("prices") or []
        if not prices:
            return None, None, "No price payload"
        p0 = prices[0]
        bid = float(p0["bids"][0]["price"])
        ask = float(p0["asks"][0]["price"])
        mid = (bid + ask) / 2
        spread_pips = (ask - bid) / (0.01 if pair.endswith("JPY") else 0.0001)
        return mid, spread_pips, "OANDA"
    except Exception as exc:
        return None, None, f"OANDA error: {exc}"


def _yf_interval(chart_interval: str) -> str:
    if chart_interval == "1h":
        return "60m"
    return chart_interval


def _period_for_interval(chart_interval: str, days: int) -> str:
    if chart_interval == "1m":
        return f"{max(1, min(days, 7))}d"
    if chart_interval in {"5m", "15m", "30m", "1h"}:
        return f"{max(1, min(days, 60))}d"
    return f"{max(1, min(days, 3650))}d"


@st.cache_data(ttl=20)
def fetch_live_intraday_yfinance(pair: str, chart_interval: str, bars: int = LIVE_HISTORY_BARS, lookback_days: int = 2) -> pd.DataFrame:
    ticker = FOREX_PAIRS.get(pair)
    if not ticker:
        return pd.DataFrame()
    interval = _yf_interval(chart_interval)
    period = _period_for_interval(chart_interval, lookback_days)
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    out = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    out.index = pd.to_datetime(out.index)
    out.index.name = "Date"
    if len(out) > bars:
        out = out.tail(bars)
    return _normalize_time_index(out)


def chart_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(9,23,31,0.55)",
        font=dict(color="#d7ecf2", family="JetBrains Mono"),
        margin=dict(l=10, r=10, t=24, b=12),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _apply_price_axis_zoom(fig: go.Figure, price_df: pd.DataFrame, y_padding_pct: float) -> None:
    if price_df.empty:
        return
    hi = float(price_df["High"].max())
    lo = float(price_df["Low"].min())
    if hi <= lo:
        return
    pad = (hi - lo) * (y_padding_pct / 100.0)
    fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)


def _apply_candle_xaxis(fig: go.Figure, use_compact_axis: bool, show_rangeslider: bool) -> None:
    rangebreaks = [dict(bounds=["sat", "mon"])] if use_compact_axis else []
    fig.update_xaxes(
        type="date",
        rangeslider_visible=show_rangeslider,
        rangeslider=dict(thickness=0.08),
        rangebreaks=rangebreaks,
        row=1,
        col=1,
    )
    fig.update_xaxes(type="date", rangebreaks=rangebreaks, row=2, col=1)


def _format_time_axis(fig: go.Figure, chart_interval: str) -> None:
    if chart_interval in {"1m", "5m", "15m", "30m", "1h"}:
        tickformat = "%d %b %H:%M"
    else:
        tickformat = "%d %b %Y"
    fig.update_xaxes(tickformat=tickformat, tickangle=0, nticks=10, row=1, col=1)
    fig.update_xaxes(tickformat=tickformat, tickangle=0, nticks=10, row=2, col=1)


def generate_strategy_signal(df: pd.DataFrame, strategy_name: str) -> pd.Series:
    """Generate lightweight signal markers for intraday charts."""

    if df.empty:
        return pd.Series(dtype=int)
    strategy = strategy_name.lower()
    signal = pd.Series(0, index=df.index, dtype=int)

    if strategy == "trend":
        long_entry = (df["EMA_20"] > df["EMA_50"]) & (df["RSI_14"] > 55)
        short_entry = (df["EMA_20"] < df["EMA_50"]) & (df["RSI_14"] < 45)
    elif strategy == "meanreversion":
        long_entry = (df["Close"] < df["BB_Lower"]) & (df["RSI_14"] < 35)
        short_entry = (df["Close"] > df["BB_Upper"]) & (df["RSI_14"] > 65)
    else:
        atr_filter = df["ATR_Pct"] > df["ATR_Pct"].rolling(60, min_periods=20).median()
        long_entry = (df["Close"] >= df["Donchian_High_20"].shift(1)) & atr_filter
        short_entry = (df["Close"] <= df["Donchian_Low_20"].shift(1)) & atr_filter

    if int(long_entry.sum()) == 0 and int(short_entry.sum()) == 0:
        # Fallback to ensure visible marker diagnostics in flat conditions.
        long_entry = df["EMA_20"] > df["EMA_50"]
        short_entry = df["EMA_20"] < df["EMA_50"]

    signal[long_entry] = 1
    signal[short_entry] = -1
    return signal


def _snap_times_to_index(times: pd.Series, target_index: pd.Index) -> pd.Series:
    """Snap timestamps to the nearest visible candle index so markers stay visible."""

    if len(target_index) == 0:
        return pd.to_datetime(times, errors="coerce")
    idx = pd.DatetimeIndex(pd.to_datetime(target_index))
    src = pd.to_datetime(times, errors="coerce")
    out: list[pd.Timestamp] = []
    for t in src:
        if pd.isna(t):
            out.append(pd.NaT)
            continue
        pos = idx.get_indexer([pd.Timestamp(t)], method="nearest")[0]
        if pos == -1:
            out.append(pd.NaT)
        else:
            out.append(idx[pos])
    return pd.Series(out, index=times.index)


def plot_live_chart(
    df: pd.DataFrame,
    pair: str,
    live_price: float | None,
    chart_interval: str,
    *,
    y_padding_pct: float,
    use_compact_axis: bool,
    show_rangeslider: bool,
    signal_series: pd.Series | None = None,
    show_signal_markers: bool = False,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.72, 0.28],
        subplot_titles=(f"{pair.replace('_', '/')} - {chart_interval} Candles", "ATR(14)"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Candles",
            increasing_line_color="#58d3f7",
            decreasing_line_color="#f4845f",
            increasing_fillcolor="rgba(88,211,247,0.35)",
            decreasing_fillcolor="rgba(244,132,95,0.35)",
            whiskerwidth=0.35,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_20"], name="EMA 20", line=dict(color="#73d2de", width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_50"], name="EMA 50", line=dict(color="#f4a261", width=1.4)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["VWAP"], name="VWAP", line=dict(color="#c4b5fd", width=1.2, dash="dot")), row=1, col=1)

    if show_signal_markers and signal_series is not None and not signal_series.empty:
        long_mark = df.loc[signal_series == 1]
        short_mark = df.loc[signal_series == -1]
        fig.add_trace(
            go.Scatter(
                x=long_mark.index,
                y=long_mark["Close"],
                mode="markers",
                name="Signal Long",
                marker=dict(symbol="triangle-up", size=11, color="#00e676", line=dict(color="#071018", width=1.5)),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=short_mark.index,
                y=short_mark["Close"],
                mode="markers",
                name="Signal Short",
                marker=dict(symbol="triangle-down", size=11, color="#ff5252", line=dict(color="#071018", width=1.5)),
            ),
            row=1,
            col=1,
        )

    if live_price is not None:
        fig.add_hline(y=live_price, line_color="#9ef01a", line_dash="dot", row=1, col=1)

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["ATR_14"],
            name="ATR 14",
            line=dict(color="#ff8fab", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(255, 143, 171, 0.15)",
        ),
        row=2,
        col=1,
    )
    _apply_candle_xaxis(fig, use_compact_axis=use_compact_axis, show_rangeslider=show_rangeslider)
    _format_time_axis(fig, chart_interval)
    _apply_price_axis_zoom(fig, df, y_padding_pct=y_padding_pct)
    fig.update_yaxes(title_text="Price", tickformat=".5f", row=1, col=1)
    fig.update_yaxes(title_text="ATR", tickformat=".5f", row=2, col=1)
    return chart_theme(fig)


def plot_orderflow_volume_chart(
    df: pd.DataFrame,
    pair: str,
    chart_interval: str,
    *,
    use_compact_axis: bool,
    show_rangeslider: bool,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.52, 0.48],
        subplot_titles=(f"{pair.replace('_', '/')} - Volume", "Order Flow"),
    )
    vol = df["Volume_Effective"] if "Volume_Effective" in df.columns else df["Volume"].fillna(0.0)
    ofi = df["Order_Flow_Imbalance"] if "Order_Flow_Imbalance" in df.columns else pd.Series(0.0, index=df.index)
    cvd = df["CVD"] if "CVD" in df.columns else pd.Series(0.0, index=df.index)
    colors = np.where(df["Close"] >= df["Open"], "rgba(0,230,118,0.75)", "rgba(255,82,82,0.75)")
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=vol,
            name="Volume",
            marker_color=colors,
            opacity=0.85,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=cvd,
            name="CVD",
            line=dict(color="#8ecae6", width=1.6),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=ofi,
            name="OFI",
            marker_color=np.where(ofi >= 0, "rgba(122,229,130,0.55)", "rgba(255,107,107,0.55)"),
            opacity=0.6,
        ),
        row=2,
        col=1,
    )
    _apply_candle_xaxis(fig, use_compact_axis=use_compact_axis, show_rangeslider=show_rangeslider)
    _format_time_axis(fig, chart_interval)
    fig.update_yaxes(title_text="Volume", row=1, col=1)
    fig.update_yaxes(title_text="CVD / OFI", row=2, col=1)
    return chart_theme(fig)


def plot_backtest_price(
    signal_df: pd.DataFrame,
    focus_strategy: str,
    trades_df: pd.DataFrame,
    *,
    y_padding_pct: float,
    use_compact_axis: bool,
    show_rangeslider: bool,
    show_trade_markers: bool,
    show_signal_markers: bool,
    marker_labels: bool,
) -> go.Figure:
    signal_col = {"Trend": "Signal_Trend", "MeanReversion": "Signal_MR", "Breakout": "Signal_BO"}[focus_strategy]
    buys = signal_df[signal_df[signal_col] == 1]
    sells = signal_df[signal_df[signal_col] == -1]
    fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], shared_xaxes=True, vertical_spacing=0.08)
    fig.add_trace(
        go.Candlestick(
            x=signal_df.index,
            open=signal_df["Open"],
            high=signal_df["High"],
            low=signal_df["Low"],
            close=signal_df["Close"],
            name="Price",
            increasing_line_color="#58d3f7",
            decreasing_line_color="#f4845f",
            increasing_fillcolor="rgba(88,211,247,0.35)",
            decreasing_fillcolor="rgba(244,132,95,0.35)",
            whiskerwidth=0.35,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(go.Scatter(x=signal_df.index, y=signal_df["EMA_20"], name="EMA 20", line=dict(color="#73d2de", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=signal_df.index, y=signal_df["EMA_50"], name="EMA 50", line=dict(color="#f4a261", width=1.5)), row=1, col=1)
    if show_signal_markers:
        fig.add_trace(
            go.Scatter(
                x=buys.index,
                y=buys["Close"],
                mode="markers",
                name="Long Signal",
                marker=dict(symbol="triangle-up", size=7, color="#7ae582", opacity=0.55),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sells.index,
                y=sells["Close"],
                mode="markers",
                name="Short Signal",
                marker=dict(symbol="triangle-down", size=7, color="#ff6b6b", opacity=0.55),
            ),
            row=1,
            col=1,
        )

    if show_trade_markers and not trades_df.empty:
        tr = trades_df.copy()
        tr["Entry_Date"] = pd.to_datetime(tr["Entry_Date"], errors="coerce")
        tr["Exit_Date"] = pd.to_datetime(tr["Exit_Date"], errors="coerce")
        start = signal_df.index.min()
        end = signal_df.index.max()
        tr = tr.loc[((tr["Entry_Date"] >= start) & (tr["Entry_Date"] <= end)) | ((tr["Exit_Date"] >= start) & (tr["Exit_Date"] <= end))].copy()
        if not tr.empty:
            tr["Entry_Date"] = _snap_times_to_index(tr["Entry_Date"], signal_df.index)
            tr["Exit_Date"] = _snap_times_to_index(tr["Exit_Date"], signal_df.index)
            long_ent = tr[tr["Direction"] == "LONG"]
            short_ent = tr[tr["Direction"] == "SHORT"]
            fig.add_trace(
                go.Scatter(
                    x=long_ent["Entry_Date"],
                    y=long_ent["Entry_Price"],
                    mode="markers+text" if marker_labels else "markers",
                    name="Long Entry",
                    marker=dict(symbol="triangle-up", size=14, color="#00e676", line=dict(color="#071018", width=2)),
                    text=["LE"] * len(long_ent),
                    textposition="top center",
                    textfont=dict(color="#c5ffd9", size=10),
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=short_ent["Entry_Date"],
                    y=short_ent["Entry_Price"],
                    mode="markers+text" if marker_labels else "markers",
                    name="Short Entry",
                    marker=dict(symbol="triangle-down", size=14, color="#ff5252", line=dict(color="#071018", width=2)),
                    text=["SE"] * len(short_ent),
                    textposition="bottom center",
                    textfont=dict(color="#ffd4d4", size=10),
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=long_ent["Exit_Date"],
                    y=long_ent["Exit_Price"],
                    mode="markers+text" if marker_labels else "markers",
                    name="Long Exit",
                    marker=dict(symbol="x", size=13, color="#8ef0c0", line=dict(width=3)),
                    text=["LX"] * len(long_ent),
                    textposition="top right",
                    textfont=dict(color="#c5ffd9", size=10),
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=short_ent["Exit_Date"],
                    y=short_ent["Exit_Price"],
                    mode="markers+text" if marker_labels else "markers",
                    name="Short Exit",
                    marker=dict(symbol="x", size=13, color="#ff9e9e", line=dict(width=3)),
                    text=["SX"] * len(short_ent),
                    textposition="bottom right",
                    textfont=dict(color="#ffd4d4", size=10),
                ),
                row=1,
                col=1,
            )
    fig.add_trace(go.Scatter(x=signal_df.index, y=signal_df["RSI_14"], name="RSI 14", line=dict(color="#d7ecf2", width=1.5)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#b85c38", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#2a9d8f", row=2, col=1)
    _apply_candle_xaxis(fig, use_compact_axis=use_compact_axis, show_rangeslider=show_rangeslider)
    _format_time_axis(fig, "1D")
    _apply_price_axis_zoom(fig, signal_df[["High", "Low"]], y_padding_pct=y_padding_pct)
    fig.update_yaxes(title_text="Price", tickformat=".5f", row=1, col=1)
    fig.update_yaxes(title_text="RSI", tickformat=".1f", row=2, col=1)
    return chart_theme(fig)


def build_strategy_scorecard(
    selected_strategies: list[str],
    portfolios_map: dict[str, pd.DataFrame | None],
    trades_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy in selected_strategies:
        p_df = portfolios_map.get(strategy)
        t_df = trades_map.get(strategy, pd.DataFrame())
        if p_df is None or p_df.empty:
            continue
        m = calc_metrics(p_df, t_df)
        long_trades = int((t_df.get("Direction", pd.Series(dtype=str)) == "LONG").sum()) if not t_df.empty else 0
        short_trades = int((t_df.get("Direction", pd.Series(dtype=str)) == "SHORT").sum()) if not t_df.empty else 0
        avg_win = float(t_df.loc[t_df["PnL"] > 0, "PnL"].mean()) if (not t_df.empty and (t_df["PnL"] > 0).any()) else 0.0
        avg_loss = float(t_df.loc[t_df["PnL"] < 0, "PnL"].mean()) if (not t_df.empty and (t_df["PnL"] < 0).any()) else 0.0
        rows.append(
            {
                "Strategy": strategy,
                "Trades": int(m["trades"]),
                "Long": long_trades,
                "Short": short_trades,
                "Win Rate %": round(float(m["win_rate"]), 2),
                "Profit Factor": round(float(m["profit_factor"]), 2),
                "Total Return %": round(float(m["total"]), 2),
                "Annual Return %": round(float(m["annual"]), 2),
                "Sharpe": round(float(m["sharpe"]), 2),
                "Max DD %": round(float(m["mdd"]), 2),
                "Avg Win": round(avg_win, 2),
                "Avg Loss": round(avg_loss, 2),
                "Net PnL": round(float(t_df["PnL"].sum()), 2) if not t_df.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_direction_table(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty or "Direction" not in trades_df.columns:
        return pd.DataFrame(columns=["Direction", "Trades", "Win Rate %", "Net PnL", "Profit Rate %"])
    rows: list[dict[str, object]] = []
    for side in ("LONG", "SHORT"):
        sub = trades_df.loc[trades_df["Direction"] == side]
        if sub.empty:
            rows.append({"Direction": side, "Trades": 0, "Win Rate %": 0.0, "Net PnL": 0.0, "Profit Rate %": 0.0})
            continue
        win_rate = (sub["PnL"] > 0).mean() * 100
        profit_rate = sub["PnL"].sum() / max(abs(sub["PnL"]).sum(), 1e-9) * 100
        rows.append(
            {
                "Direction": side,
                "Trades": int(len(sub)),
                "Win Rate %": round(float(win_rate), 2),
                "Net PnL": round(float(sub["PnL"].sum()), 2),
                "Profit Rate %": round(float(profit_rate), 2),
            }
        )
    return pd.DataFrame(rows)


def build_exit_reason_table(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty or "Exit_Reason" not in trades_df.columns:
        return pd.DataFrame(columns=["Exit Reason", "Count", "Win Rate %", "Net PnL"])
    rows: list[dict[str, object]] = []
    for reason, sub in trades_df.groupby("Exit_Reason"):
        rows.append(
            {
                "Exit Reason": reason,
                "Count": int(len(sub)),
                "Win Rate %": round(float((sub["PnL"] > 0).mean() * 100), 2),
                "Net PnL": round(float(sub["PnL"].sum()), 2),
            }
        )
    return pd.DataFrame(rows).sort_values("Count", ascending=False)


def build_signal_health_table(signal_df: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    mapping = {"Trend": "Signal_Trend", "MeanReversion": "Signal_MR", "Breakout": "Signal_BO"}
    col = mapping[strategy_name]
    if signal_df.empty or col not in signal_df.columns:
        return pd.DataFrame(columns=["Metric", "Value"])
    sig = signal_df[col].astype(int)
    changes = int((sig != sig.shift(1)).sum())
    latest = int(sig.iloc[-1])
    latest_label = "LONG" if latest == 1 else "SHORT" if latest == -1 else "FLAT"
    rows = [
        {"Metric": "Latest Signal", "Value": latest_label},
        {"Metric": "Long Bars", "Value": int((sig == 1).sum())},
        {"Metric": "Short Bars", "Value": int((sig == -1).sum())},
        {"Metric": "Flat Bars", "Value": int((sig == 0).sum())},
        {"Metric": "Signal Changes", "Value": changes},
    ]
    return pd.DataFrame(rows)


with st.sidebar:
    st.markdown("## Forex Controls")
    available_pairs = discover_pairs()
    if not available_pairs:
        st.error("No forex pairs available.")
        st.stop()

    pair = st.selectbox("Pair", available_pairs)
    live_mode = st.toggle("Live Mode", value=True)
    if live_mode:
        chart_interval = st.selectbox("Chart Interval", SUPPORTED_CHART_INTERVALS[:-1], index=2)
    else:
        chart_interval = st.selectbox("Chart Interval", SUPPORTED_CHART_INTERVALS, index=5)
    st.markdown("### Chart Controls")
    candles_on_screen = st.slider("Horizontal Candles", min_value=60, max_value=1200, value=300, step=20)
    y_padding_pct = st.slider("Vertical Padding %", min_value=2, max_value=40, value=12, step=1)
    use_compact_axis = st.toggle("TV-Style Compact Axis", value=False)
    show_rangeslider = st.toggle("Show Horizontal Slider", value=not use_compact_axis)
    scroll_zoom = st.toggle("Mouse Wheel Zoom", value=True)
    show_trade_markers = st.toggle("Show Executed Long/Short", value=True)
    marker_labels = st.toggle("Marker Labels (LE/SE/LX/SX)", value=True)
    show_signal_markers = st.toggle("Show Signal Markers", value=True)
    show_orderflow_panel = st.toggle("Show Order Flow + Volume Panel", value=True)
    auto_refresh = st.toggle("Auto Refresh 1s", value=live_mode)

    available_strategies = [name for name in STRATEGIES if Path(PORTFOLIO_DIR, f"{pair}_{name}_portfolio.csv").exists()]
    if not available_strategies:
        available_strategies = list(STRATEGIES)
    selected = st.multiselect("Strategies", available_strategies, default=available_strategies[: min(3, len(available_strategies))])
    if not selected:
        selected = available_strategies[:1]
    focus_strategy = st.selectbox("Signal Overlay", selected)

    timeline_sources = [load_portfolio(pair, name) for name in available_strategies]
    timeline_sources = [df for df in timeline_sources if df is not None and not df.empty]
    if timeline_sources:
        min_available = min(df.index.min() for df in timeline_sources).normalize()
        max_available = max(df.index.max() for df in timeline_sources).normalize()
    else:
        min_available = pd.Timestamp("2018-01-01")
        max_available = pd.Timestamp.today().normalize()

    if not live_mode:
        st.markdown("### Timeline")
        timeline_mode = st.selectbox(
            "Range",
            ["Last 30D", "Last 90D", "Last 180D", "Last 1Y", "YTD", "All", "Custom"],
            index=2,
        )
        if timeline_mode == "Custom":
            start_raw, end_raw = st.date_input(
                "Custom Range",
                value=(max(min_available, max_available - pd.Timedelta(days=180)), max_available),
                min_value=min_available.date(),
                max_value=max_available.date(),
            )
            start_date = pd.Timestamp(start_raw)
            end_date = pd.Timestamp(end_raw)
        else:
            end_date = max_available
            if timeline_mode == "All":
                start_date = min_available
            elif timeline_mode == "YTD":
                start_date = pd.Timestamp(year=end_date.year, month=1, day=1)
            elif timeline_mode == "Last 1Y":
                start_date = end_date - pd.Timedelta(days=365)
            elif timeline_mode == "Last 180D":
                start_date = end_date - pd.Timedelta(days=180)
            elif timeline_mode == "Last 90D":
                start_date = end_date - pd.Timedelta(days=90)
            else:
                start_date = end_date - pd.Timedelta(days=30)
            if start_date < min_available:
                start_date = min_available
        if start_date > end_date:
            start_date, end_date = end_date, start_date
    else:
        end_date = max_available
        start_date = max(min_available, end_date - pd.Timedelta(days=30))

    st.caption(f"Latest historical date: {max_available.date()}")
    st.caption(f"View: {start_date.date()} to {end_date.date()}")
    st.caption("Backtest: risk-based sizing, spread, slippage, ATR stops")

st.title("Forex Live + Backtest Dashboard")
st.caption(
    f"Pair: {pair.replace('_', '/')} | "
    f"Starting capital: ${INITIAL_CAPITAL:,.0f} | "
    f"Mode: {'Live Monitoring' if live_mode else 'Backtest Analytics'}"
)

if live_mode:
    section("Live Feed")
    source_note = "Yahoo 1m feed"
    live_price = None
    spread_pips = None

    oanda_price, oanda_spread, oanda_note = fetch_live_from_oanda(pair)
    if oanda_price is not None:
        live_price = oanda_price
        spread_pips = oanda_spread
        source_note = oanda_note

    lookback_days = 2 if chart_interval == "1m" else 30
    live_df = fetch_live_intraday_yfinance(pair, chart_interval=chart_interval, bars=LIVE_HISTORY_BARS, lookback_days=lookback_days)
    if live_df.empty:
        st.warning("No live bars available right now. Check internet connection or try another pair.")
    else:
        live_df = live_df.tail(candles_on_screen).copy()
        live_df = add_intraday_indicators(live_df)
        if live_price is None:
            live_price = float(live_df["Close"].iloc[-1])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Live Price", f"{live_price:.5f}")
        with c2:
            delta = float(live_df["Close"].iloc[-1] - live_df["Close"].iloc[-2]) if len(live_df) > 1 else 0.0
            metric_card(f"Last {chart_interval} Delta", f"{delta:+.5f}")
        with c3:
            atr_last = float(live_df["ATR_14"].iloc[-1]) if "ATR_14" in live_df.columns else 0.0
            metric_card("ATR 14", f"{atr_last:.5f}")
        with c4:
            spread_label = f"{spread_pips:.2f} pips" if spread_pips is not None else "N/A"
            metric_card("Spread", spread_label)

        st.caption(f"Feed source: {source_note} | Last bar: {live_df.index[-1]}")
        live_sig = generate_strategy_signal(live_df, focus_strategy)
        st.caption(
            f"Signal check ({focus_strategy}): "
            f"long={(live_sig == 1).sum()} short={(live_sig == -1).sum()}"
        )
        st.plotly_chart(
            plot_live_chart(
                live_df,
                pair,
                live_price,
                chart_interval,
                y_padding_pct=y_padding_pct,
                use_compact_axis=use_compact_axis,
                show_rangeslider=show_rangeslider,
                signal_series=live_sig,
                show_signal_markers=show_signal_markers,
            ),
            use_container_width=True,
            key=f"live_feed_chart_{pair}_{chart_interval}",
            config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
        )
        if show_orderflow_panel:
            st.plotly_chart(
                plot_orderflow_volume_chart(
                    live_df,
                    pair,
                    chart_interval,
                    use_compact_axis=use_compact_axis,
                    show_rangeslider=False,
                ),
                use_container_width=True,
                key=f"live_orderflow_{pair}_{chart_interval}",
                config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
            )

    if auto_refresh:
        st.caption(f"Auto-refreshing every {LIVE_REFRESH_SECONDS} second")

portfolios = {strategy: load_portfolio(pair, strategy) for strategy in selected}
trades = {strategy: load_trades(pair, strategy) for strategy in selected}
signal_df = load_signal_frame(pair)

portfolios = {strategy: apply_date_filter_indexed(df, start_date, end_date) for strategy, df in portfolios.items()}
trades = {strategy: apply_date_filter_trades(df, start_date, end_date) for strategy, df in trades.items()}
signal_df = apply_date_filter_indexed(signal_df, start_date, end_date)

section("Performance Snapshot")
cols = st.columns(len(selected))
for idx, strategy in enumerate(selected):
    portfolio_df = portfolios[strategy]
    if portfolio_df is None:
        continue
    metrics = calc_metrics(portfolio_df, trades[strategy])
    with cols[idx]:
        st.markdown(f"**{strategy}**")
        metric_card("Annual Return", f"{metrics['annual']:+.1f}%")
        metric_card("Sharpe", f"{metrics['sharpe']:.2f}")
        metric_card("Max Drawdown", f"{metrics['mdd']:.1f}%")
        metric_card("Trades", f"{int(metrics['trades'])}")

section("Strategy Metrics Table")
scorecard_df = build_strategy_scorecard(selected, portfolios, trades)
if scorecard_df.empty:
    st.info("No strategy metrics available for the current filters.")
else:
    st.dataframe(scorecard_df, use_container_width=True)

section("Long Short And Exit Analytics")
focus_trades = trades.get(focus_strategy, pd.DataFrame()).copy()
ls_col, exit_col = st.columns(2)
with ls_col:
    st.markdown(f"**Long/Short Breakdown - {focus_strategy}**")
    st.dataframe(build_direction_table(focus_trades), use_container_width=True)
with exit_col:
    st.markdown(f"**Exit Reason Breakdown - {focus_strategy}**")
    st.dataframe(build_exit_reason_table(focus_trades), use_container_width=True)

section("Equity Curves")
equity_fig = go.Figure()
for strategy, portfolio_df in portfolios.items():
    if portfolio_df is None or portfolio_df.empty:
        continue
    indexed = portfolio_df["Portfolio_Value"] / INITIAL_CAPITAL * 100
    equity_fig.add_trace(
        go.Scatter(
            x=indexed.index,
            y=indexed.values,
            mode="lines",
            name=strategy,
            line=dict(color=COLORS.get(strategy, "#ffffff"), width=2),
        )
    )
equity_fig.add_hline(y=100, line_color="#33586a", line_dash="dash")
equity_fig.update_yaxes(title_text="Indexed Portfolio")
st.plotly_chart(chart_theme(equity_fig), use_container_width=True, key=f"equity_curve_chart_{pair}_{'_'.join(selected)}")

section("Drawdown And Trade Distribution")
left, right = st.columns([1.25, 1])

with left:
    dd_fig = go.Figure()
    for strategy, portfolio_df in portfolios.items():
        if portfolio_df is None or portfolio_df.empty:
            continue
        dd = (portfolio_df["Portfolio_Value"] / portfolio_df["Portfolio_Value"].cummax() - 1) * 100
        dd_fig.add_trace(
            go.Scatter(
                x=dd.index,
                y=dd.values,
                fill="tozeroy",
                name=strategy,
                line=dict(color=COLORS.get(strategy, "#ffffff"), width=1.5),
            )
        )
    dd_fig.update_yaxes(title_text="Drawdown %")
    st.plotly_chart(chart_theme(dd_fig), use_container_width=True, key=f"drawdown_chart_{pair}_{'_'.join(selected)}")

with right:
    pnl_fig = go.Figure()
    for strategy, trades_df in trades.items():
        if trades_df.empty:
            continue
        pnl_fig.add_trace(
            go.Histogram(
                x=trades_df["PnL"],
                name=strategy,
                opacity=0.55,
                marker_color=COLORS.get(strategy, "#ffffff"),
                nbinsx=24,
            )
        )
    pnl_fig.update_layout(barmode="overlay")
    pnl_fig.update_xaxes(title_text="Trade PnL ($)")
    st.plotly_chart(chart_theme(pnl_fig), use_container_width=True, key=f"pnl_hist_chart_{pair}_{'_'.join(selected)}")

section("Price And Signals")
if signal_df is None or signal_df.empty:
    st.info("Signal source file not found for this pair and date window.")
else:
    sig_health = build_signal_health_table(signal_df, focus_strategy)
    if not sig_health.empty:
        st.dataframe(sig_health, use_container_width=True)
    if chart_interval == "1D":
        signal_df = signal_df.tail(candles_on_screen).copy()
        st.plotly_chart(
            plot_backtest_price(
                signal_df,
                focus_strategy,
                focus_trades,
                y_padding_pct=y_padding_pct,
                use_compact_axis=use_compact_axis,
                show_rangeslider=show_rangeslider,
                show_trade_markers=show_trade_markers,
                show_signal_markers=show_signal_markers,
                marker_labels=marker_labels,
            ),
            use_container_width=True,
            key=f"price_signals_daily_{pair}_{focus_strategy}",
            config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
        )
        if show_orderflow_panel:
            daily_with_of = add_intraday_indicators(signal_df)
            st.plotly_chart(
                plot_orderflow_volume_chart(
                    daily_with_of,
                    pair,
                    chart_interval,
                    use_compact_axis=use_compact_axis,
                    show_rangeslider=False,
                ),
                use_container_width=True,
                key=f"price_signals_orderflow_daily_{pair}_{focus_strategy}",
                config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
            )
    else:
        range_days = max(2, (end_date - start_date).days + 1)
        intraday_df = fetch_live_intraday_yfinance(pair, chart_interval=chart_interval, bars=LIVE_HISTORY_BARS, lookback_days=range_days)
        if intraday_df.empty:
            st.info("No intraday data available for selected interval. Switch to 1D or check connection.")
        else:
            intraday_df = intraday_df.tail(candles_on_screen).copy()
            intraday_df = add_intraday_indicators(intraday_df)
            intraday_sig = generate_strategy_signal(intraday_df, focus_strategy)
            st.caption(
                f"Signal check ({focus_strategy}, {chart_interval}): "
                f"long={(intraday_sig == 1).sum()} short={(intraday_sig == -1).sum()}"
            )
            st.plotly_chart(
                plot_live_chart(
                    intraday_df,
                    pair,
                    float(intraday_df["Close"].iloc[-1]),
                    chart_interval,
                    y_padding_pct=y_padding_pct,
                    use_compact_axis=use_compact_axis,
                    show_rangeslider=show_rangeslider,
                    signal_series=intraday_sig,
                    show_signal_markers=show_signal_markers,
                ),
                use_container_width=True,
                key=f"price_signals_intraday_{pair}_{focus_strategy}_{chart_interval}",
                config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
            )
            if show_orderflow_panel:
                st.plotly_chart(
                    plot_orderflow_volume_chart(
                        intraday_df,
                        pair,
                        chart_interval,
                        use_compact_axis=use_compact_axis,
                        show_rangeslider=False,
                    ),
                    use_container_width=True,
                    key=f"price_signals_orderflow_{pair}_{focus_strategy}_{chart_interval}",
                    config={"displayModeBar": True, "scrollZoom": scroll_zoom, "responsive": True},
                )

section("Trade Log")
trade_view = trades.get(focus_strategy, pd.DataFrame()).copy()
if trade_view.empty:
    st.info("No completed trades for this strategy and date window.")
else:
    show_cols = [
        "Entry_Date",
        "Exit_Date",
        "Direction",
        "Entry_Price",
        "Exit_Price",
        "Units",
        "PnL",
        "Hold_Days",
        "Exit_Reason",
    ]
    st.dataframe(trade_view[show_cols].sort_values("Exit_Date", ascending=False), use_container_width=True)

if live_mode and auto_refresh:
    time.sleep(LIVE_REFRESH_SECONDS)
    st.rerun()
