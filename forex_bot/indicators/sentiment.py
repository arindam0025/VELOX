"""
Commitment of Traders (CFTC) parsing and retail sentiment proxies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from forex_bot.config import CONFIG


@dataclass(frozen=True)
class CotRow:
    """Single weekly COT positioning snapshot."""

    report_date: pd.Timestamp
    non_commercial_net: float
    commercial_net: float


def parse_cot_csv(path: str | Path) -> pd.DataFrame:
    """
    Load a CFTC-style CSV with columns for non-commercial and commercial net.

    Expected columns (case-insensitive): ``report_date`` or ``date``,
    ``noncommercial_net`` or ``non_commercial_net``, ``commercial_net``.

    Args:
        path: Filesystem path to CSV.

    Returns:
        Normalized DataFrame sorted by date.
    """

    p = Path(path)
    raw = pd.read_csv(p)
    cols = {c.lower(): c for c in raw.columns}
    date_col = cols.get("report_date") or cols.get("date")
    if date_col is None:
        raise ValueError("COT CSV must contain report_date or date column.")
    nc_col = cols.get("noncommercial_net") or cols.get("non_commercial_net")
    c_col = cols.get("commercial_net")
    if nc_col is None or c_col is None:
        raise ValueError("COT CSV must contain commercial and non-commercial net columns.")

    out = pd.DataFrame(
        {
            "report_date": pd.to_datetime(raw[date_col], utc=True),
            "non_commercial_net": raw[nc_col].astype(float),
            "commercial_net": raw[c_col].astype(float),
        }
    )
    return out.sort_values("report_date").reset_index(drop=True)


def retail_contrarian_signal(retail_long_pct: float) -> str:
    """
    Map retail positioning percentage long to a contrarian bias label.

    Args:
        retail_long_pct: Percent of retail traders long (0-100).

    Returns:
        ``fade_longs``, ``fade_shorts``, or ``neutral``.
    """

    thr = CONFIG.thresholds.retail_sentiment_extreme_pct
    if retail_long_pct >= thr:
        return "fade_longs"
    if retail_long_pct <= 100.0 - thr:
        return "fade_shorts"
    return "neutral"
