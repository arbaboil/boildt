"""FRED data puller.

Free key. Owner already has one; store in .env as FRED_API_KEY.
"""
from __future__ import annotations

import io
import time
from datetime import date
from typing import Iterable

import pandas as pd
import requests

from src.util.config import get_key
from src.util.paths import DATA_RAW

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_series(series_id: str, api_key: str) -> pd.DataFrame:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    r = requests.get(FRED_URL, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    df = pd.DataFrame(obs)
    if df.empty:
        return pd.DataFrame(columns=["date", series_id])
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df[series_id] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", series_id]].dropna(subset=[series_id])


SERIES = {
    "DCOILWTICO": "wti_spot",
    "DCOILBRENTEU": "brent_spot",
    "DTWEXBGS": "dxy_broad",
    "DFII10": "real_yield_10y",
    "VIXCLS": "vix",
    "T10Y3M": "yc_10y_3m",
    "INDPRO": "indpro",
    "MANEMP": "manuf_emp",
    "DGS10": "nom_yield_10y",
    "BAMLH0A0HYM2": "hy_oas",
}


def pull_fred(series: Iterable[str] | None = None,
              api_key: str | None = None) -> pd.DataFrame:
    """Pull the requested FRED series and merge to a wide daily frame."""
    api_key = api_key or get_key("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY missing; put it in .env")
    series = list(series) if series is not None else list(SERIES.keys())
    frames: list[pd.DataFrame] = []
    for sid in series:
        try:
            df = _fetch_series(sid, api_key)
        except requests.HTTPError as e:
            print(f"[fred] {sid} failed: {e}")
            time.sleep(0.15)
            continue
        df = df.rename(columns={sid: SERIES.get(sid, sid.lower())})
        frames.append(df)
        time.sleep(0.15)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="date", how="outer")
    out = out.sort_values("date").reset_index(drop=True)
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DATA_RAW / "fred_macro.parquet", index=False)
    return out


if __name__ == "__main__":
    pull_fred()
