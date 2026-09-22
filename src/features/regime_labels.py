"""Regime labels for oil, used by Gate B6 (regime consistency).

A crude bull/chop/bear classifier keyed on:
  - 200-day EMA slope sign + magnitude
  - realized-vol regime (quartile of 60d annualized vol vs 5y history)

Labels:
    bull  → 200d slope > slope_thresh  (trending up)
    bear  → 200d slope < -slope_thresh (trending down)
    chop  → |200d slope| ≤ slope_thresh (range-bound, regardless of vol)

Rationale: for asymmetric-R:R trend-followers, we care most about which
side of the trend we're on. The vol quartile is preserved as a secondary
label (`vol_quartile` 1..4) in case a downstream check wants
`bull ∩ high_vol` etc.

The partition is locked here (not learned from the sample). Any change
is a PROTOCOL amendment because Gate B6 depends on stable regime edges.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features import indicators as I


# Locked constants (bump PROTOCOL version if these change).
# SLOPE_THRESHOLD calibrated on 2001-2026 WTI: 0.030 → bull 46% / chop 24% /
# bear 30%, which gives Gate B6 meaningful sample size in each regime.
SLOPE_WINDOW = 200
SLOPE_THRESHOLD = 0.030
VOL_WINDOW = 60
VOL_LOOKBACK = 252 * 5    # 5y for quartile buckets
VOL_MIN_PERIODS = 252     # 1y before we produce a vol_quartile


def label_regimes(features: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with columns [date, regime, vol_quartile, slope_200d].

    Requires `date`, `wti_close` columns. Uses forward-filled close for the
    slope + vol computation (holidays don't move price), matching the
    ffill discipline in build_features.
    """
    df = features.sort_values("date").reset_index(drop=True)
    close = df["wti_close"].astype(float).ffill()

    slope = I.slope(close, SLOPE_WINDOW)
    rv = I.realized_vol(close, VOL_WINDOW)

    # Vol quartile: rolling 5y quantile buckets, ends at t (no look-ahead).
    def _quartile(x: pd.Series) -> pd.Series:
        # For each t, quartile of rv_t within the trailing VOL_LOOKBACK window.
        out = np.full(len(x), np.nan)
        arr = x.to_numpy()
        for i in range(len(x)):
            lo = max(0, i - VOL_LOOKBACK + 1)
            window = arr[lo: i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) < VOL_MIN_PERIODS or np.isnan(arr[i]):
                continue
            q = np.searchsorted(np.quantile(valid, [0.25, 0.50, 0.75]),
                                arr[i], side="right") + 1
            out[i] = q
        return pd.Series(out, index=x.index)

    vol_quartile = _quartile(rv)

    regime = np.full(len(df), "unknown", dtype=object)
    valid_slope = slope.notna()
    regime[valid_slope & (slope > SLOPE_THRESHOLD)] = "bull"
    regime[valid_slope & (slope < -SLOPE_THRESHOLD)] = "bear"
    regime[valid_slope & (slope.abs() <= SLOPE_THRESHOLD)] = "chop"

    return pd.DataFrame({
        "date": df["date"],
        "regime": regime,
        "slope_200d": slope,
        "rv_60d": rv,
        "vol_quartile": vol_quartile,
    })
