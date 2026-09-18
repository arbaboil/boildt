"""Backtest metrics: Sharpe / Sortino / Calmar / WR / bootstrap CIs.

Convention:
- Returns are trade-level R (1R = initial stop distance).
- Sharpe uses per-trade R sequence (not daily). Report both.
- Bootstrap: block bootstrap on trade sequence for autocorrelation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    n_trades: int
    n_directional: int
    n_flat: int
    flat_rate: float                  # non-directional / total
    directional_wr: float             # win rate over directional trades (excl FLAT)
    mean_r_net: float
    median_r_net: float
    total_r_net: float
    max_dd_r: float
    sharpe_per_trade: float           # mean/std of trade R * sqrt(N/year)
    sortino_per_trade: float
    calmar_r: float                   # abs(total_r_net) / max_dd_r
    long_wr: float
    short_wr: float
    n_long: int
    n_short: int
    n_target: int
    n_stop: int
    n_time: int


def compute(trades: pd.DataFrame, reads_all: pd.DataFrame | None = None,
            trades_per_year_hint: float | None = None) -> Metrics:
    """Compute metrics.

    `reads_all` is optional: pass the full reads table (with FLAT rows) to
    compute an honest flat_rate. Otherwise flat_rate = 0.
    """
    n = len(trades)
    if n == 0:
        return Metrics(
            n_trades=0, n_directional=0, n_flat=0, flat_rate=0.0,
            directional_wr=0.0, mean_r_net=0.0, median_r_net=0.0,
            total_r_net=0.0, max_dd_r=0.0, sharpe_per_trade=0.0,
            sortino_per_trade=0.0, calmar_r=0.0,
            long_wr=0.0, short_wr=0.0, n_long=0, n_short=0,
            n_target=0, n_stop=0, n_time=0,
        )

    r = trades["r_net"].to_numpy(dtype=float)
    directional_wr = float((r > 0).mean())
    mean_r = float(r.mean())
    med_r = float(np.median(r))
    total_r = float(r.sum())

    # Max drawdown on cumulative R
    cum = np.cumsum(r)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(dd.max())

    # Sharpe / Sortino: per-trade R annualized by trades/year
    if trades_per_year_hint is None:
        # Estimate: total days between first entry & last exit → trades/year
        span = (pd.to_datetime(trades["exit_date"]).max()
                - pd.to_datetime(trades["entry_date"]).min()).days
        years = max(span / 365.25, 1e-6)
        trades_per_year = n / years
    else:
        trades_per_year = trades_per_year_hint

    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    sharpe = (mean_r / sd) * np.sqrt(trades_per_year) if sd > 0 else 0.0

    downside = r[r < 0]
    ds = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = (mean_r / ds) * np.sqrt(trades_per_year) if ds > 0 else 0.0

    calmar = total_r / max_dd if max_dd > 0 else 0.0

    long = trades[trades["direction"] == 1]
    short = trades[trades["direction"] == -1]
    long_wr = float((long["r_net"] > 0).mean()) if len(long) else 0.0
    short_wr = float((short["r_net"] > 0).mean()) if len(short) else 0.0

    n_target = int((trades["outcome"] == "TARGET").sum())
    n_stop = int((trades["outcome"] == "STOP").sum())
    n_time = int((trades["outcome"] == "TIME").sum())

    if reads_all is not None and len(reads_all) > 0:
        n_flat = int((reads_all["read"] == "FLAT").sum())
        n_total = len(reads_all)
        flat_rate = n_flat / n_total if n_total > 0 else 0.0
    else:
        n_flat = 0
        flat_rate = 0.0

    return Metrics(
        n_trades=n,
        n_directional=n,
        n_flat=n_flat,
        flat_rate=flat_rate,
        directional_wr=directional_wr,
        mean_r_net=mean_r,
        median_r_net=med_r,
        total_r_net=total_r,
        max_dd_r=max_dd,
        sharpe_per_trade=float(sharpe),
        sortino_per_trade=float(sortino),
        calmar_r=float(calmar),
        long_wr=long_wr,
        short_wr=short_wr,
        n_long=int(len(long)),
        n_short=int(len(short)),
        n_target=n_target,
        n_stop=n_stop,
        n_time=n_time,
    )


def block_bootstrap_sharpe(trades: pd.DataFrame, n_boot: int = 5000,
                           block_size: int = 5, seed: int = 42) -> dict:
    """Block-bootstrap Sharpe (per-trade) with 95% CI."""
    if trades.empty:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n_boot": 0}
    r = trades["r_net"].to_numpy(dtype=float)
    n = len(r)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    span = (pd.to_datetime(trades["exit_date"]).max()
            - pd.to_datetime(trades["entry_date"]).min()).days
    years = max(span / 365.25, 1e-6)
    tpy = n / years

    sharpes = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_size) % n for s in starts])[:n]
        sample = r[idx]
        sd = sample.std(ddof=1)
        if sd == 0:
            sharpes[b] = 0.0
        else:
            sharpes[b] = (sample.mean() / sd) * np.sqrt(tpy)
    return {
        "mean": float(sharpes.mean()),
        "ci_low": float(np.quantile(sharpes, 0.025)),
        "ci_high": float(np.quantile(sharpes, 0.975)),
        "n_boot": n_boot,
        "block_size": block_size,
    }


def block_bootstrap_expectancy(trades: pd.DataFrame, n_boot: int = 5000,
                               block_size: int = 5, seed: int = 42) -> dict:
    """Bootstrap mean R (expectancy) with 95% CI."""
    if trades.empty:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    r = trades["r_net"].to_numpy(dtype=float)
    n = len(r)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_size) % n for s in starts])[:n]
        means[b] = r[idx].mean()
    return {
        "mean": float(means.mean()),
        "ci_low": float(np.quantile(means, 0.025)),
        "ci_high": float(np.quantile(means, 0.975)),
    }


def permutation_test(trades: pd.DataFrame, n_perm: int = 1000,
                     seed: int = 42) -> dict:
    """Permutation test on the sign of R: is observed mean > 95th percentile
    of shuffled-sign distribution?
    """
    if trades.empty:
        return {"p_value": 1.0, "observed_mean": 0.0}
    r = trades["r_net"].to_numpy(dtype=float)
    n = len(r)
    rng = np.random.default_rng(seed)
    observed = r.mean()
    perm = np.empty(n_perm)
    for i in range(n_perm):
        signs = rng.choice([-1, 1], size=n)
        perm[i] = (r * signs).mean()
    p = float((perm >= observed).mean())
    return {"p_value": p, "observed_mean": float(observed), "n_perm": n_perm}
