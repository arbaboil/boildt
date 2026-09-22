"""Cost model 2x / 3x stress test for a bot candidate.

Reruns simulate() with multiplied CostModel components. Reports how each
slice's metrics degrade under increasingly hostile physical-crude
conditions (worst-case slippage).

Usage:
    python scripts/cost_stress.py --candidate results/bots/bot_v3_seed7_candidate.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import TradeConfig, simulate
from src.sim.costs import CostModel
from src.sim.metrics import block_bootstrap_sharpe, compute, permutation_test
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def _make_cost(mult: float) -> CostModel:
    return CostModel(
        commission_bps=5.0 * mult,
        slippage_bps=5.0 * mult,
        slippage_vol_multiplier=5.0 * mult,
        roll_dollars_per_barrel=0.10 * mult,
        roll_frequency_days=21,
    )


def _slice_metrics(joined, tcfg, name, start, end):
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=3000, seed=1234)
    perm = permutation_test(trades, n_perm=500, seed=1234)
    return {
        "slice": name,
        "metrics": asdict(m),
        "bootstrap_sharpe": boot,
        "permutation": perm,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand_path = Path(args.candidate)
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    genome = cand.get("best_genome") or cand.get("genome")
    vote_cfg, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    holdout_end = str(features["date"].max().date())

    results = []
    for mult in (1.0, 2.0, 3.0):
        tcfg = replace(trade_cfg, cost=_make_cost(mult))
        row = {"cost_multiplier": mult, "slices": [
            _slice_metrics(joined, tcfg, "TRAIN", *TRAIN),
            _slice_metrics(joined, tcfg, "VALIDATION", *VAL),
            _slice_metrics(joined, tcfg, "HOLDOUT", HOLDOUT_START, holdout_end),
        ]}
        results.append(row)

    out = {"candidate_source": str(cand_path), "scenarios": results}
    out_path = Path(args.out) if args.out else (
        RESULTS_BOTS / f"{cand_path.stem}_cost_stress.json"
    )
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    for row in results:
        mult = row["cost_multiplier"]
        print(f"\n=== cost_multiplier = {mult}x ===")
        for s in row["slices"]:
            m = s["metrics"]; b = s["bootstrap_sharpe"]; p = s["permutation"]
            print(f"  {s['slice']:12s} n={m['n_trades']:3d} WR={m['directional_wr']:.0%} "
                  f"R={m['mean_r_net']:+.2f} totR={m['total_r_net']:+.1f} "
                  f"S={m['sharpe_per_trade']:+.2f} CI=[{b['ci_low']:+.2f}] "
                  f"DD={m['max_dd_r']:.1f}R  perm p={p['p_value']:.3f}")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
