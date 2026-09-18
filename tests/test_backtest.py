"""Backtest correctness: cost model, ATR geometry, FLAT-no-trade."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.sim.backtest import TradeConfig, simulate
from src.sim.costs import CostModel


def _price_series(prices: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=len(prices), tz="UTC")
    return pd.DataFrame({
        "date": dates,
        "wti_close": prices,
        "wti_atr20": [1.0] * len(prices),
        "wti_atr20_pct": [0.02] * len(prices),
    })


def test_flat_reads_produce_no_trades():
    df = _price_series([100, 101, 102, 103, 104, 105])
    df["read"] = "FLAT"
    trades = simulate(df, TradeConfig(daily_cadence=True))
    assert trades.empty


def test_long_target_hit():
    prices = [100, 100, 102, 104, 106]  # entry at day 1 close = 100 → target = 100 + 3*1 = 103
    df = _price_series(prices)
    df["read"] = ["BUY"] + ["FLAT"] * (len(prices) - 1)
    trades = simulate(df, TradeConfig(k_stop=1.5, k_target=3.0, daily_cadence=True))
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["direction"] == 1
    assert t["outcome"] == "TARGET"
    assert t["r_raw"] > 1.9  # k_target/k_stop = 2R gross


def test_long_stop_hit():
    prices = [100, 100, 99, 98, 97]  # entry at 100, stop at 100 - 1.5 = 98.5
    df = _price_series(prices)
    df["read"] = ["BUY"] + ["FLAT"] * (len(prices) - 1)
    trades = simulate(df, TradeConfig(k_stop=1.5, k_target=3.0, daily_cadence=True))
    assert len(trades) == 1
    assert trades.iloc[0]["outcome"] == "STOP"
    assert trades.iloc[0]["r_raw"] < -0.95


def test_cost_reduces_r():
    prices = [100, 100, 103, 104]  # target hit
    df = _price_series(prices)
    df["read"] = ["BUY"] + ["FLAT"] * (len(prices) - 1)
    cfg = TradeConfig(cost=CostModel(commission_bps=100, slippage_bps=100),
                      daily_cadence=True)
    trades = simulate(df, cfg)
    assert trades.iloc[0]["r_net"] < trades.iloc[0]["r_raw"]


def test_short_target_hit():
    prices = [100, 100, 98, 97]  # entry 100 short, target 100 - 3 = 97
    df = _price_series(prices)
    df["read"] = ["SELL"] + ["FLAT"] * (len(prices) - 1)
    trades = simulate(df, TradeConfig(k_stop=1.5, k_target=3.0, daily_cadence=True))
    assert len(trades) == 1
    assert trades.iloc[0]["direction"] == -1
    assert trades.iloc[0]["outcome"] == "TARGET"
