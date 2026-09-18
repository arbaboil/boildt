"""Validate an evolved bot on VALIDATION + HOLDOUT slices.

Reads results/bots/bot_<tag>_seed<N>.json, rebuilds VoteConfig+TradeConfig,
runs backtest on each slice, writes results/bots/bot_<tag>_validation.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import (block_bootstrap_expectancy,
                             block_bootstrap_sharpe, compute,
                             permutation_test)
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


def _slice_metrics(features, joined, name, start, end, tcfg):
    slc = joined[(joined["date"] >= pd.to_datetime(start, utc=True))
                 & (joined["date"] <= pd.to_datetime(end, utc=True))].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades, reads_all=slc[["date", "read"]])
    boot_s = block_bootstrap_sharpe(trades, n_boot=2000)
    boot_e = block_bootstrap_expectancy(trades, n_boot=2000)
    perm = permutation_test(trades, n_perm=500)
    return {
        "slice": name, "start": start, "end": end,
        "n_rows_in_slice": int(len(slc)),
        "metrics": asdict(m),
        "bootstrap_sharpe": boot_s,
        "bootstrap_expectancy": boot_e,
        "permutation": perm,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True, help="path to bot json")
    ap.add_argument("--tag", default="validation")
    args = ap.parse_args()

    bot = json.loads(Path(args.bot).read_text(encoding="utf-8"))
    genome = bot["best_genome"]
    vote_cfg, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(reads[["date", "read", "confidence", "score", "coverage"]],
                            on="date", how="left")

    slices = [
        ("TRAIN", "2006-01-01", "2018-12-31"),
        ("VALIDATION", "2019-01-01", "2023-12-31"),
        ("HOLDOUT", "2024-01-01", str(features["date"].max().date())),
    ]
    results = [_slice_metrics(features, joined, n, s, e, trade_cfg) for n, s, e in slices]

    out = {
        "bot_source": str(args.bot),
        "genome": genome,
        "slices": results,
    }
    p = RESULTS_BOTS / f"bot_{args.tag}.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    for r in results:
        m = r["metrics"]
        b = r["bootstrap_sharpe"]
        print(f"{r['slice']:12s} n={m['n_trades']:3d} WR={m['directional_wr']:.2%} "
              f"meanR={m['mean_r_net']:+.3f} totR={m['total_r_net']:+.2f} "
              f"Sharpe={m['sharpe_per_trade']:+.2f} CI=[{b['ci_low']:+.2f},{b['ci_high']:+.2f}]")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
