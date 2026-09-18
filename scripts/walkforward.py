"""Run walk-forward K-fold validation and write results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_WALKFORWARD


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=10)
    ap.add_argument("--start", default="2001-01-01")
    ap.add_argument("--end", default=None)
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

    from src.sim.backtest import TradeConfig
    result = walkforward(features, k=args.folds,
                         cfg_trade=TradeConfig(daily_cadence=(args.cadence == "daily")),
                         seed=args.seed)

    RESULTS_WALKFORWARD.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_WALKFORWARD / f"engine_{args.engine}_{args.cadence}_k{args.folds}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "positive_expectancy_folds": result["positive_expectancy_folds"],
        "positive_sharpe_folds": result["positive_sharpe_folds"],
        "pass_7of10_rule": result["pass_7of10_rule"],
        "k": result["k"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
