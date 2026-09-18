"""Build the deterministic feature matrix from the oil_master parquet.

Output: `data/processed/features.parquet` — one row per business day, all
features known at close of that day. No look-ahead by construction (rolling
windows all end at t; consumer applies shift(1) when needed for prediction).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import indicators as I
from src.util.paths import DATA_PROCESSED


def build_features(master: pd.DataFrame | None = None) -> pd.DataFrame:
    if master is None:
        master = pd.read_parquet(DATA_PROCESSED / "oil_master.parquet")

    df = master.copy().sort_values("date").reset_index(drop=True)

    wti = df["wti_close"].astype(float)
    brent = df["brent_close"].astype(float) if "brent_close" in df else None

    out = pd.DataFrame({"date": df["date"]})
    out["wti_close"] = wti
    if brent is not None:
        out["brent_close"] = brent

    # ---- Trend / momentum
    out["wti_ret_1d"] = I.log_returns(wti)
    out["wti_ret_5d"] = np.log(wti / wti.shift(5))
    out["wti_ret_20d"] = np.log(wti / wti.shift(20))
    out["wti_ret_60d"] = np.log(wti / wti.shift(60))
    out["wti_ema20_slope"] = I.slope(I.ema(wti, 20), 20)
    out["wti_ema50_slope"] = I.slope(I.ema(wti, 50), 20)
    out["wti_ema200_slope"] = I.slope(I.ema(wti, 200), 60)
    out["wti_rsi14"] = I.rsi(wti, 14)
    out["wti_macd_hist"] = I.macd_hist(wti)
    out["wti_donchian55"] = I.donchian_position(wti, 55)

    # ---- Volatility regime
    out["wti_rv20"] = I.realized_vol(wti, 20)
    out["wti_rv60"] = I.realized_vol(wti, 60)
    out["wti_atr20"] = I.atr_from_close(wti, 20)
    out["wti_atr20_pct"] = out["wti_atr20"] / wti
    if "vix" in df:
        out["vix_z156w"] = I.zscore(df["vix"].astype(float), 156 * 5)
    if "ovx_close" in df:
        out["ovx_z"] = I.zscore(df["ovx_close"].astype(float), 156 * 5)

    # ---- Curve shape / cross-asset (crack spread proxy)
    if brent is not None:
        out["brent_wti_spread"] = brent - wti
        out["brent_wti_spread_z"] = I.zscore(out["brent_wti_spread"], 252)
    if "ho_close" in df and "rb_close" in df:
        crack = (df["ho_close"].astype(float) * 42 + df["rb_close"].astype(float) * 42) / 2 - wti
        out["crack_spread"] = crack
        out["crack_spread_z"] = I.zscore(crack, 252)

    # ---- Positioning (COT)
    if "mm_net_wti" in df:
        mm = df["mm_net_wti"].astype(float)
        out["cot_mm_net_wti"] = mm
        out["cot_mm_net_wti_z"] = I.zscore(mm, 156)  # weekly z; still valid daily-forward-filled
    if "prod_net_wti" in df:
        prod = df["prod_net_wti"].astype(float)
        out["cot_prod_net_wti_z"] = I.zscore(prod, 156)

    # ---- EIA weekly surprise (deviation from 5y seasonal median)
    if "us_crude_stocks_kb" in df:
        s = df["us_crude_stocks_kb"].astype(float)
        # weekly diff
        wchg = s.diff()
        out["eia_crude_stocks_wchg"] = wchg
        # 5y (260-week) rolling median of the weekly-change
        out["eia_stocks_surprise"] = wchg - wchg.rolling(260 * 5, min_periods=52).median()
    if "us_refinery_util_pct" in df:
        u = df["us_refinery_util_pct"].astype(float)
        out["eia_refutil_z"] = I.zscore(u, 260 * 5)

    # ---- Macro
    if "dxy_broad" in df:
        out["dxy_ret_20d"] = np.log(df["dxy_broad"].astype(float) / df["dxy_broad"].astype(float).shift(20))
    if "real_yield_10y" in df:
        out["real_yield_10y_d20"] = df["real_yield_10y"].astype(float).diff(20)
    if "yc_10y_3m" in df:
        out["yc_10y_3m"] = df["yc_10y_3m"].astype(float)
    if "indpro" in df:
        out["indpro_yoy"] = df["indpro"].astype(float).pct_change(252)
    if "hy_oas" in df:
        out["hy_oas_z"] = I.zscore(df["hy_oas"].astype(float), 252 * 3)
    if "sp500_close" in df:
        out["sp500_ret_20d"] = np.log(df["sp500_close"].astype(float) / df["sp500_close"].astype(float).shift(20))

    out = out.replace([np.inf, -np.inf], np.nan)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out.to_parquet(DATA_PROCESSED / "features.parquet", index=False)
    return out


if __name__ == "__main__":
    f = build_features()
    print(f"Features rows: {len(f):,} cols: {len(f.columns)}")
    print(f.columns.tolist())
