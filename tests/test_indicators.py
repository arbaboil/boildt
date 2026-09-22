"""Deterministic tests for indicator functions."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features import indicators as I


def _series(*vals: float) -> pd.Series:
    return pd.Series(list(vals), dtype=float)


def test_log_returns_symmetry():
    s = _series(100, 110, 121)
    r = I.log_returns(s)
    assert np.isnan(r.iloc[0])
    assert pytest.approx(r.iloc[1], rel=1e-6) == np.log(110 / 100)
    assert pytest.approx(r.iloc[2], rel=1e-6) == np.log(121 / 110)


def test_ema_stability():
    s = pd.Series(np.arange(1, 101), dtype=float)
    e = I.ema(s, 10)
    assert e.iloc[9] > 0
    assert e.iloc[99] < 100
    assert not e.iloc[99] == e.iloc[98]


def test_rsi_bounded():
    rng = np.random.default_rng(0)
    s = pd.Series(np.cumsum(rng.normal(0, 1, 500)) + 100, dtype=float)
    r = I.rsi(s, 14)
    valid = r.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_zscore_zero_mean():
    rng = np.random.default_rng(1)
    s = pd.Series(rng.normal(50, 10, 1000), dtype=float)
    z = I.zscore(s, 252)
    tail = z.iloc[-100:]
    assert abs(tail.mean()) < 0.5


def test_donchian_position_in_unit():
    rng = np.random.default_rng(2)
    s = pd.Series(np.cumsum(rng.normal(0, 1, 500)) + 100, dtype=float)
    d = I.donchian_position(s, 55)
    valid = d.dropna()
    assert (valid >= 0).all()
    assert (valid <= 1.0 + 1e-9).all()


def test_atr_from_close_populated_when_input_is_continuous():
    # 100 clean bars → ATR fully populated after warm-up. atr_from_close
    # does close.diff() (loses index 0) then rolling(20, min_periods=20),
    # so the first valid ATR sits at index 20.
    rng = np.random.default_rng(3)
    s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 100)), dtype=float)
    atr = I.atr_from_close(s, 20)
    assert atr.iloc[20:].notna().all()
    assert (atr.iloc[20:] > 0).all()
