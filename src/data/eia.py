"""EIA v2 API puller for weekly petroleum status + refinery util.

Requires EIA_API_KEY in .env. Free key.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from src.util.config import get_key
from src.util.paths import DATA_RAW

BASE = "https://api.eia.gov/v2/{route}/data/"

# Route + series-id + label
SERIES = [
    # weekly ending stocks of crude oil (excluding SPR), thousand barrels
    ("petroleum/stoc/wstk", "WCESTUS1", "us_crude_stocks_kb"),
    # weekly refinery net input of crude oil, thousand barrels/day
    ("petroleum/pnp/wiup", "WCRRIUS2", "us_refinery_input_kbd"),
    # weekly refinery utilization, percent
    ("petroleum/pnp/wiup", "WPULEUS3", "us_refinery_util_pct"),
    # weekly imports of crude oil, thousand barrels/day
    ("petroleum/move/wkly", "WCEIMUS2", "us_crude_imports_kbd"),
    # weekly exports of crude oil, thousand barrels/day
    ("petroleum/move/wkly", "WCREXUS2", "us_crude_exports_kbd"),
]


def _fetch(route: str, series_id: str, api_key: str) -> pd.DataFrame:
    url = BASE.format(route=route)
    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }
    rows: list[dict] = []
    while True:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        data = r.json().get("response", {}).get("data", [])
        if not data:
            break
        rows.extend(data)
        if len(data) < params["length"]:
            break
        params["offset"] += params["length"]
    if not rows:
        return pd.DataFrame(columns=["date", series_id])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["period"], utc=True)
    df[series_id] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", series_id]].dropna().sort_values("date")


def pull_eia(api_key: str | None = None) -> pd.DataFrame:
    api_key = api_key or get_key("EIA_API_KEY")
    if not api_key:
        # Non-fatal: return empty frame so the pipeline still runs
        print("[eia] EIA_API_KEY missing; skipping EIA pull")
        return pd.DataFrame()
    frames = []
    for route, sid, label in SERIES:
        try:
            df = _fetch(route, sid, api_key).rename(columns={sid: label})
            frames.append(df)
        except Exception as e:
            print(f"[eia] {sid} failed: {e}")
        time.sleep(0.2)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")
    out = out.sort_values("date").reset_index(drop=True)
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DATA_RAW / "eia_weekly.parquet", index=False)
    return out


if __name__ == "__main__":
    pull_eia()
