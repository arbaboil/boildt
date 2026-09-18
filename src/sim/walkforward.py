"""Walk-forward K-fold validation.

Splits the sample into K chronological non-overlapping test folds. For each
fold, the engine parameters are fixed (already tuned on TRAIN); we just
re-score and simulate on the fold slice, then aggregate.

For an engine with hand-picked defaults (v0.1) this is a pure OOS test.
For a tuned engine (v0.2+), fold-i test uses parameters fit on the
expanding-train prefix ending before fold-i.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Callable

import numpy as np
import pandas as pd

from src.engine.regime_vote import VoteConfig, score_matrix
from src.sim.backtest import TradeConfig, simulate
from src.sim.metrics import compute, block_bootstrap_sharpe


def kfold_ranges(dates: pd.Series, k: int = 10) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return K chronological non-overlapping (start, end) date ranges."""
    d = pd.to_datetime(dates).sort_values().reset_index(drop=True)
    n = len(d)
    if n < k:
        raise ValueError(f"Not enough rows ({n}) for {k}-fold split")
    edges = np.linspace(0, n, k + 1, dtype=int)
    ranges = []
    for i in range(k):
        start = d.iloc[edges[i]]
        end = d.iloc[edges[i + 1] - 1]
        ranges.append((start, end))
    return ranges


def walkforward(features: pd.DataFrame,
                cfg_vote: VoteConfig | None = None,
                cfg_trade: TradeConfig | None = None,
                k: int = 10,
                seed: int = 42) -> dict:
    cfg_vote = cfg_vote or VoteConfig()
    cfg_trade = cfg_trade or TradeConfig()

    reads = score_matrix(features, cfg_vote)
    joined = features.merge(reads[["date", "read", "confidence", "score", "coverage"]],
                            on="date", how="left")

    ranges = kfold_ranges(joined["date"], k=k)
    fold_summaries = []
    for i, (s, e) in enumerate(ranges):
        slc = joined[(joined["date"] >= s) & (joined["date"] <= e)].reset_index(drop=True)
        trades = simulate(slc, cfg_trade)
        metrics = compute(trades, reads_all=slc[["date", "read"]])
        boot = block_bootstrap_sharpe(trades, n_boot=2000, seed=seed + i)
        fold_summaries.append({
            "fold": i + 1,
            "start": str(s.date()),
            "end": str(e.date()),
            "metrics": asdict(metrics),
            "bootstrap_sharpe": boot,
        })

    # Aggregate: how many folds pass a simple positive-expectancy test?
    positive_folds = sum(1 for f in fold_summaries
                         if f["metrics"]["n_trades"] > 0
                         and f["metrics"]["mean_r_net"] > 0)
    sharpe_positive_folds = sum(1 for f in fold_summaries
                                if f["metrics"]["n_trades"] > 0
                                and f["metrics"]["sharpe_per_trade"] > 0)
    return {
        "k": k,
        "folds": fold_summaries,
        "positive_expectancy_folds": positive_folds,
        "positive_sharpe_folds": sharpe_positive_folds,
        "pass_7of10_rule": positive_folds >= 7,
    }
