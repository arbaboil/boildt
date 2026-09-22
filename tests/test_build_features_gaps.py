"""Regression tests for the ATR-through-holidays fix.

Master parquet is on a business-day calendar; US market holidays land as
NaN closes. Rolling indicators with min_periods=window used to fail on
every 20-day window that contained a holiday, wiping ATR for ~60% of
rows. build_features now forward-fills for indicator computation while
preserving the raw close so the backtest still gates on market-open days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.build import build_features


def _synthetic_master(n_days: int = 300, holiday_stride: int = 20,
                     seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n_days)))
    close_series = pd.Series(close, index=dates)
    # Punch synthetic holidays every `holiday_stride` bars
    holiday_idx = np.arange(holiday_stride, n_days, holiday_stride)
    close_series.iloc[holiday_idx] = np.nan
    return pd.DataFrame({
        "date": dates,
        "wti_close": close_series.values,
    })


def test_atr_survives_holiday_gaps():
    master = _synthetic_master(n_days=300, holiday_stride=20)
    f = build_features(master=master)

    # After 20-day warm-up, ATR should be defined for every remaining row —
    # holiday rows fill from the previous close (zero diff) but the ATR
    # itself must be a number.
    atr = f["wti_atr20"].iloc[20:]
    assert atr.notna().all(), (
        f"wti_atr20 has NaN after warm-up: "
        f"{int(atr.isna().sum())} / {len(atr)} rows"
    )
    assert (atr > 0).all()


def test_raw_wti_close_preserves_holiday_nans():
    """Backtest gates on wti_close notna. We must NOT ffill it in the output."""
    master = _synthetic_master(n_days=200, holiday_stride=20)
    f = build_features(master=master)
    holiday_rows = master["wti_close"].isna().sum()
    assert holiday_rows > 0
    assert f["wti_close"].isna().sum() == holiday_rows


def test_train_slice_atr_fully_populated():
    """On real data: TRAIN 2001-2018 must have ATR everywhere after warm-up."""
    try:
        f = pd.read_parquet("data/processed/features.parquet")
    except FileNotFoundError:
        return  # skip if features not built yet
    f["date"] = pd.to_datetime(f["date"])
    train = f[(f["date"] >= pd.Timestamp("2001-01-21", tz="UTC"))
              & (f["date"] <= pd.Timestamp("2018-12-31", tz="UTC"))]
    n_missing = int(train["wti_atr20"].isna().sum())
    # Allow a handful of leading NaNs from the master calendar edges; but
    # after the first year of TRAIN we expect zero.
    late = train[train["date"] >= pd.Timestamp("2002-01-01", tz="UTC")]
    assert late["wti_atr20"].isna().sum() == 0, (
        f"Late-TRAIN ATR still has NaNs: {int(late['wti_atr20'].isna().sum())} rows"
    )
