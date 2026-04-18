"""
OHLCV and tick data acquisition from OANDA, MetaTrader5, and yfinance.

Caching uses parquet files under ``CONFIG.paths.parquet_cache_dir`` and
optionally Redis when ``CONFIG.cache_backend`` is ``redis`` and the client is
available. All timestamps are normalized to UTC.
"""

from __future__ import annotations

import hashlib
import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

import pandas as pd
import requests

from forex_bot.config import (
    CONFIG,
    AppConfig,
    BrokerName,
    CacheBackend,
    DataSource,
    Timeframe,
)
from forex_bot.data.processor import clean_ohlcv, ensure_utc_index
from forex_bot.utils.logger import get_logger

logger = get_logger(__name__)


def _empty_ohlcv_frame() -> pd.DataFrame:
    """Return an empty OHLCV frame with a UTC DatetimeIndex."""

    idx = pd.DatetimeIndex([], tz="UTC", name="time")
    return pd.DataFrame(
        columns=["open", "high", "low", "close", "volume"], index=idx
    )


@dataclass(frozen=True)
class TickPayload:
    """Single bid/ask quote from a streaming feed."""

    time_utc: datetime
    instrument: str
    bid: float
    ask: float


def instrument_to_yfinance_ticker(instrument: str) -> str:
    """
    Map OANDA-style ``EUR_USD`` to a yfinance symbol such as ``EURUSD=X``.

    Args:
        instrument: Underscore-separated pair from configuration.

    Returns:
        Yahoo Finance ticker string.
    """

    parts = instrument.split("_")
    if len(parts) != 2:
        raise ValueError(f"Expected instrument like EUR_USD, got {instrument!r}")
    return f"{parts[0]}{parts[1]}=X"


def _timeframe_to_yfinance_interval(tf: Timeframe) -> str:
    """Map internal timeframe to yfinance interval string."""

    mapping: dict[Timeframe, str] = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1d",
    }
    if tf not in mapping:
        raise ValueError(f"Unsupported timeframe for yfinance: {tf}")
    return mapping[tf]


def _timeframe_to_oanda_granularity(tf: Timeframe) -> str:
    """OANDA v20 granularity matches enum string values (e.g. ``H1``)."""

    return tf.value


def _timeframe_to_timedelta(tf: Timeframe) -> pd.Timedelta:
    """Bar length as pandas Timedelta for pagination cursors."""

    minutes_map: dict[Timeframe, int] = {
        Timeframe.M1: 1,
        Timeframe.M5: 5,
        Timeframe.M15: 15,
        Timeframe.M30: 30,
        Timeframe.H1: 60,
        Timeframe.H4: 240,
        Timeframe.D1: 1440,
    }
    if tf not in minutes_map:
        raise ValueError(f"Unsupported timeframe for OANDA pagination: {tf}")
    return pd.Timedelta(minutes=minutes_map[tf])


def _oanda_rest_base(cfg: AppConfig) -> str:
    """Resolve OANDA REST host for practice vs live."""

    if cfg.oanda.environment.lower() == "live":
        return cfg.oanda.rest_base_url_live.rstrip("/")
    return cfg.oanda.rest_base_url_practice.rstrip("/")


def _oanda_stream_base(cfg: AppConfig) -> str:
    """Resolve OANDA streaming host for practice vs live."""

    if cfg.oanda.environment.lower() == "live":
        return cfg.oanda.stream_base_url_live.rstrip("/")
    return cfg.oanda.stream_base_url_practice.rstrip("/")


def _retry_sleep(cfg: AppConfig, attempt: int) -> None:
    """Exponential backoff delay between HTTP retries."""

    delay = cfg.data.fetch_retry_backoff_seconds * (2**attempt)
    time.sleep(delay)


def _cache_file_path(
    cfg: AppConfig,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> Path:
    """Build deterministic parquet path for a request range."""

    safe_inst = instrument.replace("/", "_")
    digest = hashlib.sha256(
        f"{safe_inst}|{timeframe.value}|{start.isoformat()}|{end.isoformat()}".encode()
    ).hexdigest()[:16]
    subdir = cfg.paths.parquet_cache_dir / safe_inst / timeframe.value
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir / f"{start.date()}_{end.date()}_{digest}.parquet"


def _read_parquet_cache(path: Path) -> pd.DataFrame | None:
    """Load parquet if the file exists."""

    if not path.is_file():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("parquet_cache_read_failed", path=str(path), error=str(exc))
        return None


def _write_parquet_cache(path: Path, df: pd.DataFrame) -> None:
    """Persist dataframe to parquet."""

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def _redis_client(cfg: AppConfig) -> Any | None:
    """Return a Redis client or None if unavailable."""

    try:
        import redis  # type: ignore[import-untyped]

        return redis.Redis.from_url(cfg.redis.url, db=cfg.redis.db, decode_responses=False)
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.debug("redis_unavailable", error=str(exc))
        return None


def _redis_cache_key(
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> str:
    """Stable Redis key for OHLCV blob."""

    h = hashlib.sha256(
        f"{instrument}|{timeframe.value}|{start.isoformat()}|{end.isoformat()}".encode()
    ).hexdigest()
    return f"ohlcv:{h}"


def _fetch_oanda_rest(
    cfg: AppConfig,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """
    Fetch mid OHLCV from OANDA REST, paginating forward in time.

    Uses ``requests`` against the v20 API (``oandapyV20`` optional wrapper not
    required for reads).
    """

    if not cfg.oanda.api_token:
        raise RuntimeError("OANDA_API_TOKEN is not set in configuration.")

    base = _oanda_rest_base(cfg)
    url = f"{base}/v3/instruments/{instrument}/candles"
    granularity = _timeframe_to_oanda_granularity(timeframe)
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    rows: list[dict[str, Any]] = []
    next_from = start_utc
    headers = {
        "Authorization": f"Bearer {cfg.oanda.api_token}",
        "Accept-Datetime-Format": "RFC3339",
    }

    for attempt in range(cfg.data.fetch_max_retries):
        try:
            while next_from < end_utc:
                params: dict[str, Any] = {
                    "granularity": granularity,
                    "price": "M",
                    "from": next_from.isoformat().replace("+00:00", "Z"),
                    "count": cfg.data.oanda_max_candles_per_request,
                }
                resp = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=cfg.data.fetch_http_timeout_seconds,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"OANDA HTTP {resp.status_code}: {resp.text}")
                payload = resp.json()
                candles = payload.get("candles") or []
                if not candles:
                    break
                for c in candles:
                    if not c.get("complete", True):
                        continue
                    t = pd.Timestamp(c["time"])
                    if t.tzinfo is None:
                        t = t.tz_localize("UTC")
                    else:
                        t = t.tz_convert("UTC")
                    if t < start_utc or t >= end_utc:
                        continue
                    mid = c.get("mid") or {}
                    rows.append(
                        {
                            "time": t,
                            "open": float(mid["o"]),
                            "high": float(mid["h"]),
                            "low": float(mid["l"]),
                            "close": float(mid["c"]),
                            "volume": int(c.get("volume", 0)),
                        }
                    )
                last_time = pd.Timestamp(candles[-1]["time"])
                if last_time.tzinfo is None:
                    last_time = last_time.tz_localize("UTC")
                else:
                    last_time = last_time.tz_convert("UTC")
                step = _timeframe_to_timedelta(timeframe)
                next_candidate = last_time + step
                if next_candidate <= last_time:
                    break
                next_from = next_candidate
                if len(candles) < cfg.data.oanda_max_candles_per_request:
                    break
            break
        except Exception:
            if attempt + 1 >= cfg.data.fetch_max_retries:
                raise
            _retry_sleep(cfg, attempt)
            logger.warning("oanda_fetch_retry", attempt=attempt + 1)

    if not rows:
        return _empty_ohlcv_frame()

    df = pd.DataFrame(rows)
    df = df.set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _fetch_mt5(
    cfg: AppConfig,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch rates from MetaTrader 5 using ``copy_rates_range``."""

    try:
        import MetaTrader5 as mt5  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("MetaTrader5 package is not installed.") from exc

    symbol = instrument.replace("_", "") if cfg.data.mt5_symbol_from_instrument else instrument
    if not mt5.initialize(path=cfg.mt5.path or None):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    try:
        tf_map = {
            Timeframe.M1: mt5.TIMEFRAME_M1,
            Timeframe.M5: mt5.TIMEFRAME_M5,
            Timeframe.M15: mt5.TIMEFRAME_M15,
            Timeframe.M30: mt5.TIMEFRAME_M30,
            Timeframe.H1: mt5.TIMEFRAME_H1,
            Timeframe.H4: mt5.TIMEFRAME_H4,
            Timeframe.D1: mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map[timeframe]
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        rates = mt5.copy_rates_range(symbol, mt5_tf, start_utc, end_utc)
        if rates is None or len(rates) == 0:
            return _empty_ohlcv_frame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "tick_volume": "volume",
            }
        )
        if "volume" not in df.columns and "real_volume" in df.columns:
            df["volume"] = df["real_volume"]
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
        return df
    finally:
        mt5.shutdown()


def _flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize MultiIndex columns from ``yfinance`` download output."""

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_yfinance(
    cfg: AppConfig,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Download historical bars using yfinance (fallback data source)."""

    try:
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("yfinance package is not installed.") from exc

    ticker = instrument_to_yfinance_ticker(instrument)
    interval = _timeframe_to_yfinance_interval(timeframe)
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    tkr = yf.Ticker(ticker)
    raw = tkr.history(
        start=start_utc,
        end=end_utc,
        interval=interval,
        auto_adjust=cfg.data.yfinance_auto_adjust,
        actions=False,
    )
    if raw is None or raw.empty:
        return _empty_ohlcv_frame()
    raw = _flatten_yfinance_columns(raw)
    raw = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    if "volume" not in raw.columns:
        raw["volume"] = 0
    idx = pd.DatetimeIndex(raw.index)
    if idx.tz is None:
        raw.index = idx.tz_localize("UTC")
    else:
        raw.index = idx.tz_convert("UTC")
    raw.index.name = "time"
    out = raw[["open", "high", "low", "close", "volume"]]
    return out


def _resolve_fetch_order(
    cfg: AppConfig,
    source: DataSource | None,
) -> Sequence[DataSource]:
    """Build an ordered list of providers to try."""

    if source is not None:
        return (source,)
    primary: DataSource
    if cfg.primary_broker == BrokerName.OANDA:
        primary = DataSource.OANDA
    elif cfg.primary_broker == BrokerName.METATRADER5:
        primary = DataSource.METATRADER5
    elif cfg.primary_broker == BrokerName.CCXT:
        primary = cfg.fallback_data_source
    else:
        primary = cfg.fallback_data_source
    order: list[DataSource] = [primary]
    if cfg.fallback_data_source not in order:
        order.append(cfg.fallback_data_source)
    for ds in (DataSource.OANDA, DataSource.METATRADER5, DataSource.YFINANCE):
        if ds not in order:
            order.append(ds)
    return tuple(order)


def fetch_ohlcv(
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    *,
    source: DataSource | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
    config: AppConfig | None = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV bars for ``instrument`` between ``start`` and ``end`` (UTC).

    Tries providers in order from configuration until one succeeds. Applies
    parquet (and optional Redis) caching when enabled.

    Args:
        instrument: Broker instrument id (e.g. ``EUR_USD`` for OANDA).
        timeframe: Candle timeframe.
        start: Range start (timezone-aware).
        end: Range end (timezone-aware).
        source: Force a specific ``DataSource``; otherwise derive from config.
        use_cache: Read/write cache when True.
        force_refresh: Skip reading cache even if present.
        config: Optional ``AppConfig`` override.

    Returns:
        DataFrame indexed by UTC time with OHLCV columns.
    """

    cfg = config or CONFIG
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware datetimes.")
    cache_path = _cache_file_path(cfg, instrument, timeframe, start, end)

    if use_cache and not force_refresh and cfg.cache_backend != CacheBackend.NONE:
        if cfg.data.parquet_cache_enabled:
            cached = _read_parquet_cache(cache_path)
            if cached is not None:
                logger.info("ohlcv_cache_hit", path=str(cache_path))
                return ensure_utc_index(cached)

        if cfg.cache_backend == CacheBackend.REDIS:
            r = _redis_client(cfg)
            if r is not None:
                key = _redis_cache_key(instrument, timeframe, start, end)
                blob = r.get(key)
                if blob:
                    buf = io.BytesIO(blob)
                    df = pd.read_parquet(buf)
                    logger.info(
                        "ohlcv_redis_hit",
                        key=key.decode() if isinstance(key, bytes) else key,
                    )
                    return ensure_utc_index(df)

    order = _resolve_fetch_order(cfg, source)
    last_error: Exception | None = None
    df_out: pd.DataFrame | None = None

    for src in order:
        try:
            if src == DataSource.OANDA:
                df_out = _fetch_oanda_rest(cfg, instrument, timeframe, start, end)
            elif src == DataSource.METATRADER5:
                df_out = _fetch_mt5(cfg, instrument, timeframe, start, end)
            elif src == DataSource.YFINANCE:
                df_out = _fetch_yfinance(cfg, instrument, timeframe, start, end)
            else:
                continue
            break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "ohlcv_fetch_failed_try_next",
                source=src.value,
                error=str(exc),
            )

    if df_out is None:
        raise RuntimeError("All data sources failed for OHLCV fetch.") from last_error

    df_out = ensure_utc_index(df_out)
    if df_out.empty:
        return df_out
    df_out = clean_ohlcv(df_out, drop_zero_volume=False)

    if use_cache and cfg.cache_backend != CacheBackend.NONE and not df_out.empty:
        try:
            if cfg.data.parquet_cache_enabled:
                _write_parquet_cache(cache_path, df_out)
            if cfg.cache_backend == CacheBackend.REDIS:
                r = _redis_client(cfg)
                if r is not None:
                    buf = io.BytesIO()
                    df_out.to_parquet(buf)
                    key = _redis_cache_key(instrument, timeframe, start, end)
                    r.setex(key, cfg.data.redis_ohlcv_ttl_seconds, buf.getvalue())
        except Exception as exc:  # pragma: no cover - cache optional
            logger.warning("ohlcv_cache_write_failed", error=str(exc))

    return df_out


def stream_oanda_prices(
    instruments: Sequence[str],
    *,
    config: AppConfig | None = None,
) -> Iterator[TickPayload]:
    """
    Stream live bid/ask ticks from OANDA's pricing stream (line-delimited JSON).

    This is a blocking generator intended for dedicated worker threads or
    async bridges. Reconnection uses ``CONFIG.data.websocket_reconnect_delay_seconds``.

    Args:
        instruments: OANDA instrument names (e.g. ``EUR_USD``).
        config: Optional ``AppConfig`` override.

    Yields:
        :class:`TickPayload` for each quote update.
    """

    cfg = config or CONFIG
    if not cfg.oanda.api_token or not cfg.oanda.account_id:
        raise RuntimeError("OANDA_API_TOKEN and OANDA_ACCOUNT_ID must be set for streaming.")

    base = _oanda_stream_base(cfg)
    url = f"{base}/v3/accounts/{cfg.oanda.account_id}/pricing/stream"
    params = {"instruments": ",".join(instruments)}
    headers = {"Authorization": f"Bearer {cfg.oanda.api_token}"}

    while True:
        try:
            with requests.get(
                url,
                headers=headers,
                params=params,
                stream=True,
                timeout=cfg.data.fetch_http_timeout_seconds,
            ) as resp:
                if resp.status_code >= 400:
                    raise RuntimeError(f"OANDA stream HTTP {resp.status_code}: {resp.text}")
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") != "PRICE":
                        continue
                    inst = msg.get("instrument")
                    if not inst:
                        continue
                    tstr = msg.get("time")
                    if not tstr:
                        continue
                    ts = pd.Timestamp(tstr)
                    if ts.tzinfo is None:
                        ts = ts.tz_localize("UTC")
                    else:
                        ts = ts.tz_convert("UTC")
                    bids = msg.get("bids") or []
                    asks = msg.get("asks") or []
                    if not bids or not asks:
                        continue
                    bid = float(bids[0]["price"])
                    ask = float(asks[0]["price"])
                    yield TickPayload(
                        time_utc=ts.to_pydatetime(),
                        instrument=str(inst),
                        bid=bid,
                        ask=ask,
                    )
        except Exception as exc:
            logger.warning("oanda_stream_reconnect", error=str(exc))
            time.sleep(cfg.data.websocket_reconnect_delay_seconds)
