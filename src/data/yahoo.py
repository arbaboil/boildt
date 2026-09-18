"""Yahoo Finance daily-bar puller via the current chart API (v8).

The legacy /v7/finance/download endpoint returns 401 as of 2024. We use
/v8/finance/chart which is still open.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from src.util.paths import DATA_RAW

BASE = "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

TICKERS = {
    "CL=F": "wti_futures_yf",
    "BZ=F": "brent_futures_yf",
    "^OVX": "ovx",
    "DX-Y.NYB": "dxy_yf",
    "^VIX": "vix_yf",
    "^GSPC": "sp500",
    "HO=F": "heating_oil",
    "RB=F": "rbob_gasoline",
    "NG=F": "natgas",
}


def _fetch(ticker: str) -> pd.DataFrame:
    params = {
        "period1": 0,
        "period2": int(time.time()),
        "interval": "1d",
        "includePrePost": "false",
        "events": "div|split",
    }
    r = requests.get(BASE.format(ticker=ticker), params=params,
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    j = r.json()
    result = (j.get("chart") or {}).get("result") or []
    if not result:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    r0 = result[0]
    ts = r0.get("timestamp") or []
    q = ((r0.get("indicators") or {}).get("quote") or [{}])[0]
    if not ts:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame({
        "date": pd.to_datetime(ts, unit="s", utc=True).normalize(),
        "open": q.get("open") or [],
        "high": q.get("high") or [],
        "low": q.get("low") or [],
        "close": q.get("close") or [],
        "volume": q.get("volume") or [],
    })
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def pull_yahoo() -> dict[str, pd.DataFrame]:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}
    for ticker, label in TICKERS.items():
        try:
            df = _fetch(ticker)
        except Exception as e:
            print(f"[yahoo] {ticker} failed: {e}")
            df = pd.DataFrame()
        out[label] = df
        df.to_parquet(DATA_RAW / f"yahoo_{label}.parquet", index=False)
        time.sleep(0.5)
    return out


if __name__ == "__main__":
    pull_yahoo()
