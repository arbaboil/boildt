"""Genome-sensitivity analysis for bot v3 seed 7.

For each key weight in seed 7's genome, perturb by +/-5%, +/-10%, +/-20%
(one at a time, all others held), then re-simulate on TRAIN and
VALIDATION. Report the resulting Sharpe CI-low, WR, and mean_R.

If Sharpe CI-low stays > 0 on VAL across all +/-10% perturbations, the
strategy is robust — not knife-edge dependent on the exact tuned values.
If many perturbations flip the sign, seed 7 is over-tuned and shipping
is risky.

Output:
  results/bots/bot_v3_seed7_candidate_sensitivity.json
  human-readable per-gene table on stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import GENE_SPEC, genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import block_bootstrap_sharpe, compute
from src.util.paths import DATA_PROCESSED

TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")

# Genes we perturb (skip discretization thresholds — those are non-linear).
SENSITIVITY_GENES = [
    "w_trend", "w_momentum", "w_vol", "w_curve", "w_cot", "w_eia", "w_macro",
    "strong", "moderate", "min_coverage",
    "k_stop", "k_target", "max_hold_days",
]

PCTS = [-0.20, -0.10, -0.05, 0.0, +0.05, +0.10, +0.20]


def _clip_to_gene_bounds(genome: dict, name: str, val: float) -> float:
    for gn, lo, hi, kind in GENE_SPEC:
        if gn == name:
            v = min(max(val, lo), hi)
            if kind == "int":
                v = int(round(v))
            return float(v)
    return float(val)


def _run_slice(features: pd.DataFrame, genome: dict, name: str,
                start: str, end: str) -> dict:
    vote_cfg, trade_cfg = genome_to_configs(genome)
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, trade_cfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=1500, seed=1234)
    return {
        "slice": name,
        "n_trades": m.n_trades,
        "wr": m.directional_wr,
        "mean_r_net": m.mean_r_net,
        "sharpe": m.sharpe_per_trade,
        "sharpe_ci_low": boot["ci_low"],
        "max_dd_r": m.max_dd_r,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="results/bots/bot_v3_seed7_candidate.json")
    ap.add_argument("--out", default="results/bots/bot_v3_seed7_candidate_sensitivity.json")
    args = ap.parse_args()

    cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    base_genome = cand.get("genome") or cand.get("best_genome")

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features.sort_values("date").reset_index(drop=True)

    # Baseline metric with unperturbed genome
    baseline_train = _run_slice(features, base_genome, "TRAIN", *TRAIN)
    baseline_val = _run_slice(features, base_genome, "VALIDATION", *VAL)
    print(f"Baseline: TRAIN CIlo={baseline_train['sharpe_ci_low']:+.2f} WR={baseline_train['wr']:.0%}  "
          f"VAL CIlo={baseline_val['sharpe_ci_low']:+.2f} WR={baseline_val['wr']:.0%}")
    print()

    per_gene: dict = {}
    n_val_ci_flip = 0
    total_perturbations = 0
    for gene in SENSITIVITY_GENES:
        base_val = base_genome[gene]
        per_gene[gene] = {"base_value": base_val, "perturbations": []}
        for pct in PCTS:
            new_val = _clip_to_gene_bounds(base_genome, gene, base_val * (1 + pct))
            if pct == 0.0 or new_val == base_val:
                continue
            perturbed = dict(base_genome)
            perturbed[gene] = new_val
            tr = _run_slice(features, perturbed, "TRAIN", *TRAIN)
            va = _run_slice(features, perturbed, "VALIDATION", *VAL)
            entry = {
                "pct": pct,
                "new_value": new_val,
                "TRAIN": tr,
                "VALIDATION": va,
            }
            per_gene[gene]["perturbations"].append(entry)
            total_perturbations += 1
            if va["sharpe_ci_low"] <= 0:
                n_val_ci_flip += 1
            tag = " <=== VAL CI flipped negative" if va["sharpe_ci_low"] <= 0 else ""
            print(f"{gene:15s}  {pct:+.0%}  new={new_val:.3f}  "
                  f"TRAIN CIlo={tr['sharpe_ci_low']:+.2f} WR={tr['wr']:.0%}  "
                  f"VAL CIlo={va['sharpe_ci_low']:+.2f} WR={va['wr']:.0%}{tag}")

    verdict = {
        "n_perturbations": total_perturbations,
        "n_val_ci_flipped_negative": n_val_ci_flip,
        "frac_val_ci_flipped": n_val_ci_flip / total_perturbations if total_perturbations else 0,
        "robust": n_val_ci_flip == 0,
        "assessment": (
            "ROBUST — all perturbations keep VAL Sharpe CI positive"
            if n_val_ci_flip == 0
            else f"KNIFE-EDGE RISK — {n_val_ci_flip}/{total_perturbations} perturbations flip VAL CI negative"
        ),
    }
    print()
    print(f"=== SENSITIVITY VERDICT ===")
    print(f"  perturbations: {total_perturbations}")
    print(f"  VAL Sharpe CI flipped negative: {n_val_ci_flip}")
    print(f"  assessment: {verdict['assessment']}")

    out = {
        "candidate": args.candidate,
        "baseline": {"TRAIN": baseline_train, "VALIDATION": baseline_val},
        "sensitivity_genes": SENSITIVITY_GENES,
        "pcts": PCTS,
        "per_gene": per_gene,
        "verdict": verdict,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
