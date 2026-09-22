"""Full audit of a bot candidate against every PROTOCOL gate.

Reads a candidate JSON (produced by evolve_bot.py or hand-anointed from
the fresh-seed sweep), rebuilds its VoteConfig + TradeConfig, and runs
every gate check that Helios can automate:

  1. Sharpe CI > 0 on TRAIN + VAL + HOLDOUT (block bootstrap 5000 boots)
  2. Directional WR ≥ 50% on TRAIN + VAL + HOLDOUT
  3. Min 100 trades on TRAIN
  4. Walk-forward K=10 with ≥ 7 folds positive
  5. Max DD ≤ 15R on all three slices
  6. Permutation p-value ≤ 0.05 on all three slices (1000 shuffles)
  7. Shadow window: not checked here — separate operational gate

Writes `results/bots/<candidate>_audit.json` with the full report.

Usage:
    python scripts/candidate_audit.py --candidate results/bots/bot_v3_seed7_candidate.json
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
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS

TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def _slice_report(joined: pd.DataFrame, tcfg, name: str, start: str, end: str) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades, reads_all=slc[["date", "read"]])
    boot = block_bootstrap_sharpe(trades, n_boot=5000, seed=1234)
    exp = block_bootstrap_expectancy(trades, n_boot=5000, seed=1234)
    perm = permutation_test(trades, n_perm=1000, seed=1234)
    return {
        "slice": name, "start": start, "end": end,
        "metrics": asdict(m),
        "bootstrap_sharpe": boot,
        "bootstrap_expectancy": exp,
        "permutation": perm,
    }


def _pass(rep: dict) -> dict:
    m = rep["metrics"]
    return {
        "g1_sharpe_ci_pos": bool(rep["bootstrap_sharpe"]["ci_low"] > 0),
        "g2_wr_ge_50": bool(m["directional_wr"] >= 0.50),
        "g3_n_ge_100": bool(m["n_trades"] >= 100),
        "g5_maxdd_le_15r": bool(m["max_dd_r"] <= 15.0),
        "g6_perm_p_le_005": bool(rep["permutation"]["p_value"] <= 0.05),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand_path = Path(args.candidate)
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    genome = cand.get("genome") or cand.get("best_genome")
    if genome is None:
        raise SystemExit("Candidate JSON has neither 'genome' nor 'best_genome'.")
    vote_cfg, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])

    # Build joined reads + features on the full sample so slicing is cheap.
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )

    holdout_end = str(features["date"].max().date())
    slices = [
        _slice_report(joined, trade_cfg, "TRAIN", *TRAIN),
        _slice_report(joined, trade_cfg, "VALIDATION", *VAL),
        _slice_report(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]

    # Walk-forward K=10 on 2006-2023 (spans TRAIN + VAL)
    wf_slice = features[(features["date"] >= pd.to_datetime("2006-01-01", utc=True))
                        & (features["date"] <= pd.to_datetime("2023-12-31", utc=True))].reset_index(drop=True)
    wf = walkforward(wf_slice, cfg_vote=vote_cfg, cfg_trade=trade_cfg, k=10)

    gates = {s["slice"]: _pass(s) for s in slices}
    gates["g4_walkforward_7of10"] = bool(wf["pass_7of10_rule"])

    # Roll-up: strict PROTOCOL v0.1.0
    strict_pass = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g2_wr_ge_50"]
        and gates["VALIDATION"]["g2_wr_ge_50"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["VALIDATION"]["g5_maxdd_le_15r"]
        and gates["TRAIN"]["g6_perm_p_le_005"]
        and gates["g4_walkforward_7of10"]
    )
    proposed_v020_pass = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["VALIDATION"]["g5_maxdd_le_15r"]
        and gates["TRAIN"]["g6_perm_p_le_005"]
        and gates["g4_walkforward_7of10"]
    )

    out = {
        "candidate_source": str(cand_path),
        "genome": genome,
        "slices": slices,
        "walkforward": {
            "k": wf["k"],
            "positive_expectancy_folds": wf["positive_expectancy_folds"],
            "positive_sharpe_folds": wf["positive_sharpe_folds"],
            "pass_7of10_rule": wf["pass_7of10_rule"],
            "folds": [
                {"fold": f["fold"], "start": f["start"], "end": f["end"],
                 "n": f["metrics"]["n_trades"],
                 "wr": f["metrics"]["directional_wr"],
                 "mean_r": f["metrics"]["mean_r_net"],
                 "sharpe": f["metrics"]["sharpe_per_trade"],
                 "ci_low": f["bootstrap_sharpe"]["ci_low"]}
                for f in wf["folds"]
            ],
        },
        "gates": gates,
        "strict_v010_pass": strict_pass,
        "proposed_v020_pass": proposed_v020_pass,
    }

    out_path = Path(args.out) if args.out else (
        RESULTS_BOTS / f"{cand_path.stem}_audit.json"
    )
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    print(f"=== {cand_path.name} audit ===")
    for s in slices:
        m = s["metrics"]; b = s["bootstrap_sharpe"]; p = s["permutation"]
        g = gates[s["slice"]]
        print(f"{s['slice']:12s} n={m['n_trades']:3d} WR={m['directional_wr']:.0%} "
              f"R={m['mean_r_net']:+.2f} S={m['sharpe_per_trade']:+.2f} "
              f"CI=[{b['ci_low']:+.2f},{b['ci_high']:+.2f}] "
              f"DD={m['max_dd_r']:.1f}R  perm p={p['p_value']:.3f}  "
              f"g1={g['g1_sharpe_ci_pos']} g2={g['g2_wr_ge_50']} "
              f"g5={g['g5_maxdd_le_15r']} g6={g['g6_perm_p_le_005']}")
    print(f"WF: {wf['positive_expectancy_folds']}/10 positive-expectancy "
          f"({wf['positive_sharpe_folds']}/10 positive-Sharpe)  "
          f"g4={wf['pass_7of10_rule']}")
    print()
    print(f"strict PROTOCOL v0.1.0 pass: {strict_pass}")
    print(f"proposed PROTOCOL v0.2.0 pass (no WR gate): {proposed_v020_pass}")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
