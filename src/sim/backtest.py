"""Backtest harness.

Given a feature+read table with columns [date, wti_close, wti_atr20,
wti_atr20_pct, read], simulate an ATR-geometry trade for each non-FLAT
read. Enter next-bar-open (proxy = next close), stop = k_stop * ATR20 in
adverse direction, target = k_target * ATR20. Exit whichever hits first,
or hard time-stop at max_hold. Cost model from `costs.py`.

Metrics computed in R-units (1R = initial stop distance in $) as well as
raw log-returns for Sharpe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from src.sim.costs import CostModel


@dataclass
class TradeConfig:
    k_stop: float = 1.5
    k_target: float = 3.0
    max_hold_days: int = 20
    daily_cadence: bool = False   # False = weekly (fires only on gate day)
    entry_gate_day: int = 4       # 0=Mon ... 4=Fri (Friday close analog for weekly)
    cost: CostModel = field(default_factory=CostModel)


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    direction: int           # +1 long / -1 short
    entry_px: float
    exit_px: float
    stop_px: float
    target_px: float
    atr20: float
    r_raw: float             # PnL in R before cost
    r_net: float             # PnL in R after cost
    cost_bps: float
    outcome: str             # "TARGET" | "STOP" | "TIME"
    read: str
    hold_days: int


def _next_valid_index(df: pd.DataFrame, i: int) -> int | None:
    """Return the next row index with non-NaN wti_close, or None."""
    n = len(df)
    j = i
    while j < n:
        if pd.notna(df.iloc[j]["wti_close"]):
            return j
        j += 1
    return None


def simulate(features_with_read: pd.DataFrame,
             cfg: TradeConfig | None = None) -> pd.DataFrame:
    cfg = cfg or TradeConfig()
    df = features_with_read.sort_values("date").reset_index(drop=True)
    df["dow"] = pd.to_datetime(df["date"]).dt.dayofweek
    atr_median = df["wti_atr20_pct"].rolling(252, min_periods=60).median()

    trades: list[Trade] = []
    i = 0
    n = len(df)
    while i < n - 2:
        row = df.iloc[i]
        read = row.get("read", "FLAT")
        # Gate: weekly cadence only fires on entry_gate_day; daily fires any BD
        gate_ok = cfg.daily_cadence or row["dow"] == cfg.entry_gate_day
        # No new position if not directional or gate closed
        if read in ("FLAT",) or not gate_ok:
            i += 1
            continue
        direction = 1 if read in ("BUY", "STRONG_BUY") else -1
        atr20 = row["wti_atr20"]
        atr_pct = row["wti_atr20_pct"]
        px_now = row["wti_close"]
        if pd.isna(atr20) or pd.isna(px_now) or atr20 <= 0 or px_now <= 0:
            i += 1
            continue

        # Entry at next close (proxy for next-bar open)
        j0 = _next_valid_index(df, i + 1)
        if j0 is None:
            break
        entry_px = df.iloc[j0]["wti_close"]
        stop_px = entry_px - direction * cfg.k_stop * atr20
        target_px = entry_px + direction * cfg.k_target * atr20

        exit_px = entry_px
        outcome = "TIME"
        j_exit = min(j0 + cfg.max_hold_days, n - 1)
        for j in range(j0 + 1, j_exit + 1):
            px = df.iloc[j]["wti_close"]
            if pd.isna(px):
                continue
            hit_stop = (direction == 1 and px <= stop_px) or (direction == -1 and px >= stop_px)
            hit_target = (direction == 1 and px >= target_px) or (direction == -1 and px <= target_px)
            if hit_stop and hit_target:
                # If both cross in same day, be honest — stop hit first (worse outcome)
                exit_px = stop_px
                outcome = "STOP"
                j_exit = j
                break
            if hit_stop:
                exit_px = stop_px
                outcome = "STOP"
                j_exit = j
                break
            if hit_target:
                exit_px = target_px
                outcome = "TARGET"
                j_exit = j
                break
            exit_px = px

        # Cost (roundtrip) — apply against entry price notional
        atr_med_now = atr_median.iloc[i]
        cost_bps = cfg.cost.roundtrip_bps(atr_pct, atr_med_now)
        cost_dollars = entry_px * cost_bps / 1e4

        # Convert PnL to R
        r_denom = cfg.k_stop * atr20
        pnl_gross = direction * (exit_px - entry_px)
        pnl_net = pnl_gross - cost_dollars
        r_raw = pnl_gross / r_denom
        r_net = pnl_net / r_denom

        trades.append(Trade(
            entry_date=df.iloc[j0]["date"],
            exit_date=df.iloc[j_exit]["date"],
            direction=direction,
            entry_px=float(entry_px),
            exit_px=float(exit_px),
            stop_px=float(stop_px),
            target_px=float(target_px),
            atr20=float(atr20),
            r_raw=float(r_raw),
            r_net=float(r_net),
            cost_bps=float(cost_bps),
            outcome=outcome,
            read=read,
            hold_days=int(j_exit - j0),
        ))
        # Cool-off: no new entry until this one closes
        i = j_exit + 1

    return pd.DataFrame([t.__dict__ for t in trades])
