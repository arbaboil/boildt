"""Stooq CSV puller (best-effort; site now serves a JS challenge on many
endpoints so we treat this as optional pre-2000 backfill only)."""
from __future__ import annotations

import io

import pandas as pd
import requests

from src.util.paths import DATA_RAW

BASE = "https://stooq.com/q/d/l/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
}

SYMBOLS = {
    "cl.f": "wti_futures",
    "cb.f": "brent_futures",
    "xoi.us": "xoi_index",
}


def _fetch(symbol: str) -> pd.DataFrame:
    params = {"s": symbol, "i": "d"}
    try:
        r = requests.get(BASE, params=params, headers=HEADERS, timeout=15)
    except Exception:
        return pd.DataFrame()
    if r.status_code != 200:
        return pd.DataFrame()
    text = r.text.strip()
    if not text or "<html" in text.lower()[:200]:
        return pd.DataFrame()
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        return pd.DataFrame()
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in df.columns]
    return df[keep].sort_values("date").reset_index(drop=True)


def pull_stooq() -> dict[str, pd.DataFrame]:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}
    for sym, label in SYMBOLS.items():
        df = _fetch(sym)
        out[label] = df
        df.to_parquet(DATA_RAW / f"stooq_{label}.parquet", index=False)
    return out


if __name__ == "__main__":
    pull_stooq()
