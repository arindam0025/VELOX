"""
Data acquisition, cleaning, and session utilities.

Public surface is intentionally small; import submodules for advanced use.
"""

from forex_bot.data.fetcher import (
    TickPayload,
    fetch_ohlcv,
    stream_oanda_prices,
)
from forex_bot.data.processor import (
    clean_ohlcv,
    ensure_utc_index,
    normalize_ohlcv,
    resample_ohlcv,
)
from forex_bot.data.session_filter import (
    SessionFlags,
    annotate_sessions,
    get_session_flags,
)

__all__ = [
    "TickPayload",
    "annotate_sessions",
    "clean_ohlcv",
    "ensure_utc_index",
    "fetch_ohlcv",
    "get_session_flags",
    "normalize_ohlcv",
    "resample_ohlcv",
    "SessionFlags",
    "stream_oanda_prices",
]
