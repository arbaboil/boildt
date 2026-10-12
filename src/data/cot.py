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

# CFTC renamed the WTI NYMEX contract from "CRUDE OIL, LIGHT SWEET - NEW YORK
# MERCANTILE EXCHANGE" to "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE" after
# the 2022-02-01 report. The contract market code (067651) was preserved —
# query by code to get a continuous series across the rename. Previous
# puller used the pre-rename name and silently dropped all WTI reports after
# 2022-02-01, leaving `cot_mm_net_wti` at NaN for the entire HOLDOUT.
CONTRACT_CODES = {
    "WTI": "067651",     # NYMEX WTI Physical (ex "CRUDE OIL, LIGHT SWEET")
    "BRENT": "06765T",   # NYMEX Brent Last Day
}


def _fetch(cftc_code: str) -> pd.DataFrame:
    all_rows: list[dict] = []
    offset = 0
    limit = 5000
    while True:
        params = {
            "$where": f"cftc_contract_market_code='{cftc_code}'",
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
    for label, code in CONTRACT_CODES.items():
        try:
            df = _fetch(code)
        except Exception as e:
            print(f"[cot] {label} failed: {e}")
            df = pd.DataFrame()
        out[label] = df
        df.to_parquet(DATA_RAW / f"cot_{label.lower()}.parquet", index=False)
    return out


if __name__ == "__main__":
    pull_cot()
