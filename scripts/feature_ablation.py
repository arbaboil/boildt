"""Feature ablation study for a bot candidate.

Zero-out each vote group weight one at a time and remeasure metrics on
TRAIN + VAL + HOLDOUT. Identifies which features are load-bearing (dropping
them wrecks the strategy) vs cosmetic (dropping them has no effect).

Complements the sweep's convergent-shape finding: sweep showed the shape,
ablation shows *which channel actually drives the signal.*

Usage:
    python scripts/feature_ablation.py --candidate results/bots/bot_v3_seed7_candidate.json
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
from src.sim.metrics import block_bootstrap_sharpe, compute, permutation_test
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"

VOTE_GROUPS = ["trend", "momentum", "vol", "curve", "cot", "eia", "macro"]


def _slice_metrics(joined, tcfg, name, start, end):
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=2000, seed=1234)
    return {"slice": name, "metrics": asdict(m), "bootstrap_sharpe": boot}


def _run_with_genome(genome, features, trade_cfg, holdout_end):
    vote_cfg, _ = genome_to_configs(genome)
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    return [
        _slice_metrics(joined, trade_cfg, "TRAIN", *TRAIN),
        _slice_metrics(joined, trade_cfg, "VALIDATION", *VAL),
        _slice_metrics(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand_path = Path(args.candidate)
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    genome = cand.get("best_genome") or cand.get("genome")
    _, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    holdout_end = str(features["date"].max().date())

    # Baseline
    baseline_slices = _run_with_genome(genome, features, trade_cfg, holdout_end)

    ablated = {}
    for group in VOTE_GROUPS:
        gene = f"w_{group}"
        if gene not in genome:
            continue
        g_zero = dict(genome)
        g_zero[gene] = 0.0
        slices = _run_with_genome(g_zero, features, trade_cfg, holdout_end)
        ablated[group] = {
            "original_weight": genome[gene],
            "slices": slices,
        }

    out = {
        "candidate_source": str(cand_path),
        "baseline": baseline_slices,
        "ablated": ablated,
    }
    out_path = Path(args.out) if args.out else (
        RESULTS_BOTS / f"{cand_path.stem}_ablation.json"
    )
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    def _totr(slices, sname):
        for s in slices:
            if s["slice"] == sname:
                return s["metrics"]["total_r_net"]
        return 0.0

    def _sharpe(slices, sname):
        for s in slices:
            if s["slice"] == sname:
                return s["metrics"]["sharpe_per_trade"]
        return 0.0

    def _n(slices, sname):
        for s in slices:
            if s["slice"] == sname:
                return s["metrics"]["n_trades"]
        return 0

    print(f"=== Feature ablation — {cand_path.name} ===")
    print(f"Baseline:")
    for s in baseline_slices:
        m = s["metrics"]; b = s["bootstrap_sharpe"]
        print(f"  {s['slice']:10s} n={m['n_trades']:3d} totR={m['total_r_net']:+.1f} "
              f"S={m['sharpe_per_trade']:+.2f} CI=[{b['ci_low']:+.2f}]")

    print(f"\nAblation deltas (baseline - ablated). Bigger positive = "
          f"more load-bearing.")
    print(f"{'group':10s} {'wt':>6}  "
          f"{'d_totR TR':>10} {'d_S TR':>7} {'d_n TR':>8}  "
          f"{'d_totR VA':>10} {'d_S VA':>7} {'d_n VA':>8}  "
          f"{'d_totR HO':>10} {'d_S HO':>7} {'d_n HO':>8}")
    for group, data in ablated.items():
        wt = data["original_weight"]
        slc = data["slices"]
        dtr_tr = _totr(baseline_slices, "TRAIN") - _totr(slc, "TRAIN")
        dsh_tr = _sharpe(baseline_slices, "TRAIN") - _sharpe(slc, "TRAIN")
        dn_tr = _n(baseline_slices, "TRAIN") - _n(slc, "TRAIN")
        dtr_va = _totr(baseline_slices, "VALIDATION") - _totr(slc, "VALIDATION")
        dsh_va = _sharpe(baseline_slices, "VALIDATION") - _sharpe(slc, "VALIDATION")
        dn_va = _n(baseline_slices, "VALIDATION") - _n(slc, "VALIDATION")
        dtr_ho = _totr(baseline_slices, "HOLDOUT") - _totr(slc, "HOLDOUT")
        dsh_ho = _sharpe(baseline_slices, "HOLDOUT") - _sharpe(slc, "HOLDOUT")
        dn_ho = _n(baseline_slices, "HOLDOUT") - _n(slc, "HOLDOUT")
        print(f"{group:10s} {wt:6.2f}  "
              f"{dtr_tr:+10.1f} {dsh_tr:+7.2f} {dn_tr:+8d}  "
              f"{dtr_va:+10.1f} {dsh_va:+7.2f} {dn_va:+8d}  "
              f"{dtr_ho:+10.1f} {dsh_ho:+7.2f} {dn_ho:+8d}")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
