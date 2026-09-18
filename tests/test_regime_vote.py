"""Tests for the regime-vote engine — mostly no-look-ahead + FLAT semantics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.engine.regime_vote import VoteConfig, score_matrix, score_row


def _make_features(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2020-01-01", periods=n, tz="UTC")
    return pd.DataFrame({
        "date": dates,
        "wti_ema50_slope": rng.normal(0.0, 0.05, n),
        "wti_ret_20d": rng.normal(0.0, 0.05, n),
        "vix_z156w": rng.normal(0.0, 1.0, n),
        "crack_spread_z": rng.normal(0.0, 1.0, n),
        "cot_mm_net_wti_z": rng.normal(0.0, 1.0, n),
        "eia_stocks_surprise": rng.normal(0.0, 3000.0, n),
        "dxy_ret_20d": rng.normal(0.0, 0.02, n),
    })


def test_all_nan_returns_flat():
    df = pd.DataFrame({
        "date": pd.bdate_range("2020-01-01", periods=5, tz="UTC"),
        "wti_ema50_slope": [np.nan] * 5,
        "wti_ret_20d": [np.nan] * 5,
    })
    out = score_matrix(df, VoteConfig())
    assert (out["read"] == "FLAT").all()


def test_length_preserved():
    df = _make_features(50)
    out = score_matrix(df, VoteConfig())
    assert len(out) == 50
    assert (out["date"].values == df["date"].values).all()


def test_read_values_are_valid():
    df = _make_features(100)
    out = score_matrix(df, VoteConfig())
    allowed = {"STRONG_BUY", "BUY", "FLAT", "SELL", "STRONG_SELL"}
    assert set(out["read"].unique()).issubset(allowed)


def test_row_and_matrix_agree_on_sample():
    df = _make_features(20)
    cfg = VoteConfig()
    out = score_matrix(df, cfg)
    for i in range(20):
        s = score_row(df.iloc[i], cfg)
        assert out.iloc[i]["read"] == s["read"]


def test_extreme_bull_features_get_buy():
    """When every group points bullish, the engine should not emit FLAT."""
    df = pd.DataFrame({
        "date": [pd.Timestamp("2020-06-01", tz="UTC")],
        "wti_ema50_slope": [0.5],
        "wti_ret_20d": [0.20],
        "vix_z156w": [-2.0],       # cold vol = mildly bullish
        "crack_spread_z": [2.0],   # strong bull
        "cot_mm_net_wti_z": [-2.0],  # extreme short = bullish reversal
        "eia_stocks_surprise": [-8000.0],  # big drawdown = bullish
        "dxy_ret_20d": [-0.05],    # USD down = bullish
    })
    out = score_matrix(df, VoteConfig())
    assert out.iloc[0]["read"] in ("BUY", "STRONG_BUY")


def test_extreme_bear_features_get_sell():
    df = pd.DataFrame({
        "date": [pd.Timestamp("2020-06-01", tz="UTC")],
        "wti_ema50_slope": [-0.5],
        "wti_ret_20d": [-0.20],
        "vix_z156w": [3.0],
        "crack_spread_z": [-2.0],
        "cot_mm_net_wti_z": [2.5],
        "eia_stocks_surprise": [8000.0],
        "dxy_ret_20d": [0.05],
    })
    out = score_matrix(df, VoteConfig())
    assert out.iloc[0]["read"] in ("SELL", "STRONG_SELL")
