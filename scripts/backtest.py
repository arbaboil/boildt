"""Run a backtest of the regime-vote engine over a chosen slice.

Usage:
    python scripts/backtest.py                        # full sample
    python scripts/backtest.py --start 2001-01-01 --end 2018-12-31 --tag train
    python scripts/backtest.py --cadence daily        # daily cadence
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.regime_vote import VoteConfig, score_matrix
from src.sim.backtest import TradeConfig, simulate
from src.sim.metrics import (block_bootstrap_expectancy, block_bootstrap_sharpe,
                             compute, permutation_test)
from src.util.paths import DATA_PROCESSED, RESULTS_BACKTESTS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--tag", default="full")
    ap.add_argument("--cadence", choices=["weekly", "daily"], default="weekly")
    ap.add_argument("--engine", default="v0")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    if args.start:
        features = features[features["date"] >= pd.to_datetime(args.start, utc=True)]
    if args.end:
        features = features[features["date"] <= pd.to_datetime(args.end, utc=True)]
    features = features.reset_index(drop=True)

    reads = score_matrix(features, VoteConfig())
    joined = features.merge(reads[["date", "read", "confidence", "score", "coverage"]],
                            on="date", how="left")

    tcfg = TradeConfig(daily_cadence=(args.cadence == "daily"))
    trades = simulate(joined, tcfg)

    metrics = compute(trades, reads_all=reads)
    boot_sharpe = block_bootstrap_sharpe(trades, seed=args.seed)
    boot_exp = block_bootstrap_expectancy(trades, seed=args.seed)
    perm = permutation_test(trades, seed=args.seed)

    RESULTS_BACKTESTS.mkdir(parents=True, exist_ok=True)
    out = {
        "engine": args.engine,
        "tag": args.tag,
        "cadence": args.cadence,
        "start": str(features["date"].min()),
        "end": str(features["date"].max()),
        "metrics": asdict(metrics),
        "bootstrap_sharpe": boot_sharpe,
        "bootstrap_expectancy": boot_exp,
        "permutation": perm,
        "seed": args.seed,
    }
    dest_json = RESULTS_BACKTESTS / f"engine_{args.engine}_{args.tag}_{args.cadence}.json"
    dest_json.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    if not trades.empty:
        trades.to_parquet(RESULTS_BACKTESTS
                          / f"engine_{args.engine}_{args.tag}_{args.cadence}_trades.parquet",
                          index=False)

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
