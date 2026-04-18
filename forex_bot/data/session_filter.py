"""
Forex session detection in UTC using configurable session windows.

All timestamps must be timezone-aware; inputs are normalized to UTC before
classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any

import pandas as pd

from forex_bot.config import CONFIG, AppConfig, SessionConfig, SessionWindow


@dataclass(frozen=True)
class SessionFlags:
    """Boolean flags describing which sessions are active for a UTC instant."""

    asian: bool
    london: bool
    new_york: bool
    london_ny_overlap: bool


def _to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC, raising if naive."""

    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (use UTC).")
    return dt.astimezone(timezone.utc)


def _hour_in_window(hour: int, window: SessionWindow) -> bool:
    """
    Return True if ``hour`` falls in ``[start, end)`` on a 0–24 hour scale.

    If ``end <= start``, the window is treated as wrapping past midnight
    (not required by default session definitions).
    """

    start = window.start_hour_utc
    end = window.end_hour_utc
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def get_session_flags(
    dt_utc: datetime,
    sessions: SessionConfig | None = None,
) -> SessionFlags:
    """
    Classify a UTC timestamp against configured forex sessions.

    Args:
        dt_utc: Timezone-aware instant (any tz); converted to UTC.
        sessions: Optional session configuration (defaults to ``CONFIG.sessions``).

    Returns:
        Flags for Asian, London, New York, and London–NY overlap windows.
    """

    cfg = sessions or CONFIG.sessions
    utc_dt = _to_utc(dt_utc)
    hour = utc_dt.hour
    overlap = _hour_in_window(hour, cfg.london_ny_overlap)
    london = _hour_in_window(hour, cfg.london)
    new_york = _hour_in_window(hour, cfg.new_york)
    asian = _hour_in_window(hour, cfg.asian)
    return SessionFlags(
        asian=asian,
        london=london,
        new_york=new_york,
        london_ny_overlap=overlap,
    )


def annotate_sessions(
    df: pd.DataFrame,
    sessions: SessionConfig | None = None,
    *,
    config: AppConfig | None = None,
) -> pd.DataFrame:
    """
    Add session indicator columns aligned to the DataFrame index (UTC).

    Columns: ``session_asian``, ``session_london``, ``session_new_york``,
    ``session_overlap``.

    Args:
        df: DataFrame with a DatetimeIndex.
        sessions: Optional session configuration.
        config: Optional full config (unused; reserved for future localization).

    Returns:
        A copy of ``df`` with four boolean columns added.
    """

    _ = config
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a DatetimeIndex.")
    out = df.copy()
    sess = sessions or CONFIG.sessions

    def _row_flags(ts: pd.Timestamp) -> SessionFlags:
        if ts.tz is None:
            raise ValueError("Index timestamps must be timezone-aware (UTC).")
        dt = ts.tz_convert("UTC").to_pydatetime()
        return get_session_flags(dt, sess)

    flags = out.index.map(lambda ts: _row_flags(ts))
    out["session_asian"] = [f.asian for f in flags]
    out["session_london"] = [f.london for f in flags]
    out["session_new_york"] = [f.new_york for f in flags]
    out["session_overlap"] = [f.london_ny_overlap for f in flags]
    return out


def session_bounds_utc(
    day: datetime,
    window: SessionWindow,
) -> tuple[datetime, datetime]:
    """
    Return UTC [start, end) datetimes for a session window on ``day``'s date.

    Used for aligning session-level features (e.g. prior session high/low).

    Args:
        day: Any instant on the calendar day of interest (timezone-aware).
        window: Session window in UTC hours.

    Returns:
        Tuple of (inclusive start, exclusive end) in UTC.
    """

    utc = _to_utc(day).date()
    start = datetime.combine(utc, time(hour=window.start_hour_utc), tzinfo=timezone.utc)
    end = datetime.combine(utc, time(hour=window.end_hour_utc), tzinfo=timezone.utc)
    if end <= start:
        raise NotImplementedError("Overnight windows require explicit date handling.")
    return start, end


def as_utc_timestamp(value: Any) -> pd.Timestamp:
    """
    Coerce a scalar to a UTC pandas Timestamp with timezone awareness.

    Args:
        value: datetime-like or pandas Timestamp.

    Returns:
        Timezone-aware UTC ``pd.Timestamp``.
    """

    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return ts.tz_convert("UTC")
