"""Tests for regime label computation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.regime_labels import (SLOPE_THRESHOLD, VOL_MIN_PERIODS,
                                         label_regimes)


def _synth(n: int, drift: float, vol: float, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2010-01-01", periods=n, freq="B", tz="UTC")
    logrets = rng.normal(drift, vol, size=n)
    close = 75.0 * np.exp(np.cumsum(logrets))
    return pd.DataFrame({"date": dates, "wti_close": close})


def test_bull_regime_detected():
    # Strong uptrend: drift 0.003/day over 1500 bars → price grows ~90×.
    # At the very high tail prices, |slope| is huge; verify bull dominates.
    df = _synth(1500, drift=0.003, vol=0.008, seed=1)
    labels = label_regimes(df)
    tail = labels.iloc[-500:]
    tail = tail[tail["regime"] != "unknown"]
    assert (tail["regime"] == "bull").mean() >= 0.7


def test_bear_regime_detected():
    # Bear direction: start from a *high* base price so the absolute-dollar
    # slope threshold has real magnitude to work with. Price decays from
    # 500 downwards; even after 1500 bars it stays above ~5, so daily
    # slope magnitude stays above SLOPE_THRESHOLD.
    df = _synth(1500, drift=-0.002, vol=0.008, seed=2)
    df["wti_close"] *= 500.0 / 75.0  # rescale so bear-slope stays visible
    labels = label_regimes(df)
    tail = labels.iloc[-500:]
    tail = tail[tail["regime"] != "unknown"]
    assert (tail["regime"] == "bear").mean() >= 0.7


def test_chop_regime_detected():
    # Very-low-drift and low-vol synthetic series → dominantly chop.
    # We use vol=0.001 so the random walk doesn't drift enough to cross the
    # (real-world-calibrated) SLOPE_THRESHOLD=0.030.
    df = _synth(1500, drift=0.0, vol=0.001, seed=3)
    labels = label_regimes(df)
    tail = labels.iloc[-500:]
    tail = tail[tail["regime"] != "unknown"]
    assert (tail["regime"] == "chop").mean() >= 0.6


def test_all_three_regimes_appear_on_real_data():
    """On the real WTI feature set, every regime must have meaningful sample.
    Otherwise Gate B6 (regime consistency) is vacuous.
    """
    try:
        f = pd.read_parquet("data/processed/features.parquet")
    except FileNotFoundError:
        return
    f["date"] = pd.to_datetime(f["date"])
    f = f[f["date"] >= pd.Timestamp("2001-01-01", tz="UTC")].reset_index(drop=True)
    labels = label_regimes(f)
    dist = labels["regime"].value_counts(normalize=True)
    for r in ("bull", "chop", "bear"):
        assert dist.get(r, 0.0) >= 0.10, (
            f"regime '{r}' too rare on real data: {dist.get(r, 0.0):.1%}"
        )


def test_vol_quartile_bounded():
    df = _synth(1500, drift=0.0, vol=0.02, seed=4)
    labels = label_regimes(df)
    q = labels["vol_quartile"].dropna()
    assert q.min() >= 1 and q.max() <= 4
    # Need at least ~VOL_MIN_PERIODS rows before any quartile assigned.
    assert labels["vol_quartile"].iloc[:VOL_MIN_PERIODS - 1].isna().all()


def test_no_lookahead_slope_shape():
    """slope_200d at row t depends only on rows ≤ t."""
    df = _synth(500, drift=0.0005, vol=0.01, seed=5)
    labels_full = label_regimes(df)
    # Truncate input at row 400 and recompute — the first 400 rows of the
    # truncated labels must exactly match the first 400 of the full run.
    df_trunc = df.iloc[:400].reset_index(drop=True)
    labels_trunc = label_regimes(df_trunc)
    a = labels_full["slope_200d"].iloc[:400].to_numpy()
    b = labels_trunc["slope_200d"].iloc[:400].to_numpy()
    diff = np.where(np.isnan(a) & np.isnan(b), 0.0, np.abs(a - b))
    assert np.nanmax(diff) < 1e-9
