"""Master join: produce a single daily-frequency oil parquet.

Contract:
- Index: business-day UTC dates
- Columns: wti_close, brent_close, dxy, real_yield_10y, vix, yc_10y_3m,
           mm_net_wti, mm_net_brent, us_crude_stocks_kb,
           us_refinery_util_pct, us_crude_imports_kbd, us_crude_exports_kbd
- Weekly / monthly sources are forward-filled up to the configured lag
- Missing prefix rows keep NaN (feature layer decides)
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.util.paths import DATA_PROCESSED, DATA_RAW


def _read_parquet_safe(path):
    try:
        return pd.read_parquet(path)
    except (FileNotFoundError, OSError):
        return pd.DataFrame()


def build_master() -> pd.DataFrame:
    fred = _read_parquet_safe(DATA_RAW / "fred_macro.parquet")
    stooq_wti = _read_parquet_safe(DATA_RAW / "stooq_wti_futures.parquet")
    stooq_brent = _read_parquet_safe(DATA_RAW / "stooq_brent_futures.parquet")
    yf_wti = _read_parquet_safe(DATA_RAW / "yahoo_wti_futures_yf.parquet")
    yf_brent = _read_parquet_safe(DATA_RAW / "yahoo_brent_futures_yf.parquet")
    cot_wti = _read_parquet_safe(DATA_RAW / "cot_wti.parquet")
    cot_brent = _read_parquet_safe(DATA_RAW / "cot_brent.parquet")
    eia = _read_parquet_safe(DATA_RAW / "eia_weekly.parquet")

    # WTI daily close (prefer FRED spot; fill gaps from stooq futures)
    wti = pd.DataFrame(columns=["date", "wti_close"])
    if not fred.empty and "wti_spot" in fred.columns:
        wti = fred[["date", "wti_spot"]].rename(columns={"wti_spot": "wti_close"})
    if not stooq_wti.empty:
        s = stooq_wti[["date", "close"]].rename(columns={"close": "wti_close_futures"})
        wti = wti.merge(s, on="date", how="outer")
        wti["wti_close"] = wti["wti_close"].fillna(wti.get("wti_close_futures"))
        wti = wti.drop(columns=[c for c in ("wti_close_futures",) if c in wti.columns])
    if not yf_wti.empty:
        y = yf_wti[["date", "close"]].rename(columns={"close": "wti_close_yf"})
        wti = wti.merge(y, on="date", how="outer")
        wti["wti_close"] = wti["wti_close"].fillna(wti.get("wti_close_yf"))
        wti = wti.drop(columns=[c for c in ("wti_close_yf",) if c in wti.columns])

    brent = pd.DataFrame(columns=["date", "brent_close"])
    if not fred.empty and "brent_spot" in fred.columns:
        brent = fred[["date", "brent_spot"]].rename(columns={"brent_spot": "brent_close"})
    if not stooq_brent.empty:
        s = stooq_brent[["date", "close"]].rename(columns={"close": "brent_close_futures"})
        brent = brent.merge(s, on="date", how="outer")
        brent["brent_close"] = brent["brent_close"].fillna(brent.get("brent_close_futures"))
        brent = brent.drop(columns=[c for c in ("brent_close_futures",) if c in brent.columns])
    if not yf_brent.empty:
        y = yf_brent[["date", "close"]].rename(columns={"close": "brent_close_yf"})
        brent = brent.merge(y, on="date", how="outer")
        brent["brent_close"] = brent["brent_close"].fillna(brent.get("brent_close_yf"))
        brent = brent.drop(columns=[c for c in ("brent_close_yf",) if c in brent.columns])

    df = wti.merge(brent, on="date", how="outer")

    # Macro from FRED
    if not fred.empty:
        macro_cols = [c for c in ("dxy_broad", "real_yield_10y", "vix",
                                  "yc_10y_3m", "indpro", "ism_pmi",
                                  "nom_yield_10y", "hy_oas") if c in fred.columns]
        df = df.merge(fred[["date"] + macro_cols], on="date", how="outer")

    # COT weekly (join on date; forward-fill up to 8 business days)
    if not cot_wti.empty:
        c = cot_wti[["date", "mm_net", "prod_net", "oi_total"]].rename(
            columns={"mm_net": "mm_net_wti", "prod_net": "prod_net_wti",
                     "oi_total": "oi_total_wti"})
        df = df.merge(c, on="date", how="outer")
    if not cot_brent.empty:
        c = cot_brent[["date", "mm_net", "prod_net", "oi_total"]].rename(
            columns={"mm_net": "mm_net_brent", "prod_net": "prod_net_brent",
                     "oi_total": "oi_total_brent"})
        df = df.merge(c, on="date", how="outer")

    # EIA weekly
    if not eia.empty:
        df = df.merge(eia, on="date", how="outer")

    # Yahoo cross-asset (heating oil, RBOB gasoline, natgas, S&P, OVX)
    def _yahoo_close(name: str, label: str) -> pd.DataFrame:
        path = DATA_RAW / f"yahoo_{name}.parquet"
        try:
            y = pd.read_parquet(path)
        except (FileNotFoundError, OSError):
            return pd.DataFrame(columns=["date", label])
        if y.empty:
            return pd.DataFrame(columns=["date", label])
        return y[["date", "close"]].rename(columns={"close": label})

    for name, label in [
        ("heating_oil", "ho_close"),
        ("rbob_gasoline", "rb_close"),
        ("natgas", "ng_close"),
        ("sp500", "sp500_close"),
        ("ovx", "ovx_close"),
    ]:
        y = _yahoo_close(name, label)
        if not y.empty:
            df = df.merge(y, on="date", how="outer")

    df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    # Business-day index from earliest to latest
    if df.empty or df["date"].isna().all():
        return df
    start = df["date"].min()
    end = df["date"].max()
    idx = pd.DataFrame({"date": pd.bdate_range(start=start, end=end, tz="UTC")})
    df = idx.merge(df, on="date", how="left")

    # Forward-fill slow-cadence columns (weekly/monthly) up to 8 business days.
    slow_cols = [c for c in df.columns if any(k in c for k in (
        "mm_net", "prod_net", "oi_total", "us_crude_stocks", "us_refinery",
        "us_crude_imports", "us_crude_exports", "indpro", "ism_pmi",
        "hy_oas"))]
    if slow_cols:
        df[slow_cols] = df[slow_cols].ffill(limit=8)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    df.to_parquet(DATA_PROCESSED / f"oil_master_{stamp}.parquet", index=False)
    df.to_parquet(DATA_PROCESSED / "oil_master.parquet", index=False)
    return df


if __name__ == "__main__":
    df = build_master()
    print(f"Master rows: {len(df):,} cols: {list(df.columns)}")
