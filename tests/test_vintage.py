"""Tests for publication-lag look-ahead prevention."""
from __future__ import annotations

import pandas as pd

from src.features.vintage import safe_asof


def test_daily_source_no_lag():
    ts = pd.Timestamp("2024-03-14")
    assert safe_asof("fred_daily", ts) == ts.normalize()


def test_cot_three_bd_lag():
    ts = pd.Timestamp("2024-03-14")  # Thursday
    got = safe_asof("cot", ts)
    # 3 BD before Thursday = the prior Monday
    assert got == pd.Timestamp("2024-03-11")


def test_eia_four_bd_lag():
    ts = pd.Timestamp("2024-03-14")  # Thursday
    got = safe_asof("eia", ts)
    # 4 BD before Thursday = prior Friday (skips weekend)
    assert got == pd.Timestamp("2024-03-08")


def test_unknown_source_no_lag():
    ts = pd.Timestamp("2024-03-14")
    assert safe_asof("mystery", ts) == ts.normalize()
