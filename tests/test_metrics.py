"""Metrics + bootstrap tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.sim.metrics import (block_bootstrap_expectancy,
                             block_bootstrap_sharpe, compute,
                             permutation_test)


def _fake_trades(rs: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(rs), tz="UTC")
    return pd.DataFrame({
        "entry_date": dates,
        "exit_date": dates,
        "direction": [1] * len(rs),
        "r_net": rs,
        "r_raw": rs,
        "outcome": ["TARGET" if r > 0 else "STOP" for r in rs],
    })


def test_empty_trades_zero_metrics():
    m = compute(pd.DataFrame(columns=["entry_date", "exit_date", "direction",
                                       "r_net", "r_raw", "outcome"]))
    assert m.n_trades == 0
    assert m.directional_wr == 0.0


def test_all_wins():
    t = _fake_trades([1.0, 1.5, 2.0])
    m = compute(t)
    assert m.n_trades == 3
    assert m.directional_wr == 1.0
    assert m.mean_r_net == 1.5
    assert m.max_dd_r == 0.0


def test_mixed_pnl_wr_and_sharpe():
    t = _fake_trades([1.0, -1.0, 2.0, -0.5, 1.5])
    m = compute(t)
    assert m.n_trades == 5
    assert m.directional_wr == 0.6
    assert m.sharpe_per_trade != 0


def test_bootstrap_ci_reasonable():
    rng = np.random.default_rng(42)
    r = rng.normal(0.3, 1.0, 200).tolist()
    t = _fake_trades(r)
    boot = block_bootstrap_sharpe(t, n_boot=500)
    assert boot["ci_low"] <= boot["mean"] <= boot["ci_high"]


def test_permutation_test_produces_p():
    r = [1.0, 1.0, 1.0, 1.0, 1.0, -0.2, -0.2, -0.2, -0.2, -0.2]
    t = _fake_trades(r)
    out = permutation_test(t, n_perm=500)
    assert 0.0 <= out["p_value"] <= 1.0
