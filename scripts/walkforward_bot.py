"""Run walk-forward K-fold using an evolved bot's VoteConfig + TradeConfig."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_WALKFORWARD


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True)
    ap.add_argument("--folds", type=int, default=10)
    ap.add_argument("--start", default="2006-01-01")
    ap.add_argument("--end", default="2023-12-31")
    ap.add_argument("--tag", default="bot_walkforward")
    args = ap.parse_args()

    bot = json.loads(Path(args.bot).read_text(encoding="utf-8"))
    vote_cfg, trade_cfg = genome_to_configs(bot["best_genome"])

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features[(features["date"] >= pd.to_datetime(args.start, utc=True))
                        & (features["date"] <= pd.to_datetime(args.end, utc=True))]
    features = features.reset_index(drop=True)

    result = walkforward(features, k=args.folds, cfg_vote=vote_cfg,
                         cfg_trade=trade_cfg)

    RESULTS_WALKFORWARD.mkdir(parents=True, exist_ok=True)
    out = RESULTS_WALKFORWARD / f"{args.tag}.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print(f"positive_expectancy_folds: {result['positive_expectancy_folds']}/{result['k']}")
    print(f"positive_sharpe_folds:     {result['positive_sharpe_folds']}/{result['k']}")
    print(f"pass_7_of_10_rule:         {result['pass_7of10_rule']}")
    for f in result["folds"]:
        m = f["metrics"]
        b = f["bootstrap_sharpe"]
        print(f"  Fold {f['fold']:2d} [{f['start']}..{f['end']}]  "
              f"n={m['n_trades']:3d} WR={m['directional_wr']:.2%} "
              f"meanR={m['mean_r_net']:+.3f} Sharpe={m['sharpe_per_trade']:+.2f} "
              f"CI=[{b['ci_low']:+.2f},{b['ci_high']:+.2f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
