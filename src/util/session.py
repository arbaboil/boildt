"""Trading-session helpers shared by the live pipeline.

Two rules live here so every live script agrees on them:

1. **Completed-bar rule.** A daily bar dated D (UTC midnight) is treated as
   final only once ``now >= D + BAR_CLOSE_HOUR_UTC``. NYMEX WTI settles at
   14:30 ET (18:30/19:30 UTC); 22:00 UTC leaves margin for Yahoo/FRED to
   publish the settle. Before that, Yahoo returns an *in-progress* bar for D
   (the CME session for D opens ~22:00 UTC on D-1), which must never feed a
   published call. Discovered 2026-11-10: late-slipping crons (00:00-03:00
   UTC) were emitting calls off partial bars.

2. **Weekly signal rule.** The validated bot (genome ``daily_cadence=False``,
   ``entry_gate_day=4``) reads on the *Friday* close and enters at the next
   close. The live weekly call for the week starting Monday M therefore uses
   the last completed bar on or before Friday M-3, and is publishable from
   Friday ~22:00 UTC, well before the week opens.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

BAR_CLOSE_HOUR_UTC = 22


def utc_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def _as_utc(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def last_complete_bar_date(now=None) -> pd.Timestamp:
    """Latest bar date (UTC midnight) whose session has closed at ``now``."""
    now = _as_utc(now if now is not None else utc_now())
    d = (now - pd.Timedelta(hours=BAR_CLOSE_HOUR_UTC)).normalize()
    return d


def drop_incomplete_bars(df: pd.DataFrame, now=None,
                         date_col: str = "date") -> pd.DataFrame:
    """Drop rows whose bar has not closed yet at ``now``."""
    cutoff = last_complete_bar_date(now)
    dates = pd.to_datetime(df[date_col])
    if dates.dt.tz is None:
        dates = dates.dt.tz_localize("UTC")
    return df[dates <= cutoff].reset_index(drop=True)


def last_weekday_on_or_before(d) -> pd.Timestamp:
    d = _as_utc(d).normalize()
    while d.dayofweek >= 5:
        d -= pd.Timedelta(days=1)
    return d


def weekly_signal_friday(now=None) -> pd.Timestamp:
    """Friday whose close drives the most recent publishable weekly call."""
    d = last_complete_bar_date(now)
    return d - pd.Timedelta(days=(d.dayofweek - 4) % 7)


def week_of_for_signal_friday(friday) -> tuple[str, str]:
    """(Monday, Sunday) of the week the Friday signal is traded in."""
    monday = _as_utc(friday).normalize() + pd.Timedelta(days=3)
    return str(monday.date()), str((monday + pd.Timedelta(days=6)).date())
