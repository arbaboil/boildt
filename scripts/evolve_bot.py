"""Run the genetic algorithm to evolve a HELIOS bot on the TRAIN slice."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.evolve import evolve
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2006-01-01")   # need COT (post-2006)
    ap.add_argument("--end", default="2018-12-31")     # TRAIN only
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--pop", type=int, default=64)
    ap.add_argument("--gens", type=int, default=25)
    ap.add_argument("--elite", type=int, default=4)
    ap.add_argument("--sigma", type=float, default=0.12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features[(features["date"] >= pd.to_datetime(args.start, utc=True))
                         & (features["date"] <= pd.to_datetime(args.end, utc=True))]
    features = features.reset_index(drop=True)

    print(f"Evolving on {args.start}..{args.end}  ({len(features):,} rows)  "
          f"pop={args.pop}  gens={args.gens}  folds={args.folds}  seed={args.seed}")
    result = evolve(features, k_folds=args.folds, pop_size=args.pop,
                    n_gens=args.gens, elite=args.elite, sigma=args.sigma,
                    seed=args.seed, verbose=True)

    RESULTS_BOTS.mkdir(parents=True, exist_ok=True)
    out = {
        "best_genome": result["best_ever"]["genome"],
        "best_fitness": result["best_ever"]["fitness"],
        "best_report": result["best_ever"]["report"],
        "history_summary": [{"gen": h["gen"], "best": h["best_fitness"],
                             "median": h["median_fitness"]}
                            for h in result["history"]],
        "n_gens": result["n_gens"],
        "pop_size": result["pop_size"],
        "seed": result["seed"],
        "elapsed_s": result["elapsed_s"],
        "start": args.start,
        "end": args.end,
    }
    p = RESULTS_BOTS / f"bot_{args.tag}_seed{args.seed}.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nBest fitness: {result['best_ever']['fitness']:+.3f}")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
