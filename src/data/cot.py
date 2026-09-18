"""CFTC Commitments of Traders puller.

Disaggregated managed-money for WTI + Brent. Weekly cadence.
Uses the SODA API since it's stable + free.
"""
from __future__ import annotations

import pandas as pd
import requests

from src.util.paths import DATA_RAW

# CFTC's disaggregated futures-only (aggregated across all contract months)
BASE = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

# Market_and_Exchange_Names values
CONTRACTS = {
    "WTI": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
    "BRENT": "BRENT LAST DAY - NEW YORK MERCANTILE EXCHANGE",
}


def _fetch(market_name: str) -> pd.DataFrame:
    all_rows: list[dict] = []
    offset = 0
    limit = 5000
    while True:
        params = {
            "$where": f"market_and_exchange_names='{market_name}'",
            "$limit": limit,
            "$offset": offset,
            "$order": "report_date_as_yyyy_mm_dd DESC",
        }
        r = requests.get(BASE, params=params, timeout=60)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
    keep_map = {
        "date": "date",
        "m_money_positions_long_all": "mm_long",
        "m_money_positions_short_all": "mm_short",
        "prod_merc_positions_long": "prod_long",
        "prod_merc_positions_short": "prod_short",
        "open_interest_all": "oi_total",
    }
    have = {k: v for k, v in keep_map.items() if k in df.columns}
    df = df[list(have.keys())].rename(columns=have)
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["mm_net"] = df["mm_long"] - df["mm_short"]
    df["prod_net"] = df["prod_long"] - df["prod_short"]
    return df.sort_values("date").reset_index(drop=True)


def pull_cot() -> dict[str, pd.DataFrame]:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}
    for label, market in CONTRACTS.items():
        try:
            df = _fetch(market)
        except Exception as e:
            print(f"[cot] {label} failed: {e}")
            df = pd.DataFrame()
        out[label] = df
        df.to_parquet(DATA_RAW / f"cot_{label.lower()}.parquet", index=False)
    return out


if __name__ == "__main__":
    pull_cot()
