"""Publication delays for each data source.

`safe_asof(source, as_of_date)` returns the latest observation date for that
source that would be publicly known at close of business on `as_of_date`.
Feature code should slice with `df[df.date <= safe_asof(source, as_of)]`.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Final

import pandas as pd

# Business-day publication lags per source
PUB_LAG_BD: Final[dict[str, int]] = {
    "fred_daily": 0,      # FRED daily series (WTI, Brent, VIX, DXY, yields) — same day
    "fred_monthly": 15,   # INDPRO, MANEMP — ~15 BD lag
    "cot": 3,             # CFTC report Friday for Tuesday snapshot
    "eia": 4,             # EIA weekly Wednesday for prior week (safer +4 BD)
    "opec": 14,           # MOMR monthly ~14 BD lag
    "baker_hughes": 5,    # weekly Friday
    "yahoo": 0,           # cross-asset daily closes
    "noaa": 1,            # weather next-day
    "gdelt": 0,           # near real-time
}


def safe_asof(source: str, as_of: pd.Timestamp | date) -> pd.Timestamp:
    """Return the latest source observation date known by close of `as_of`."""
    ts = pd.Timestamp(as_of).tz_localize(None).normalize()
    lag = PUB_LAG_BD.get(source, 0)
    if lag == 0:
        return ts
    return (ts - pd.tseries.offsets.BDay(lag)).normalize()
