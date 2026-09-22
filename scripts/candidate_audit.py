"""Full audit of a bot candidate against every PROTOCOL v0.2.0 gate.

Reads a candidate JSON (produced by evolve_bot.py or hand-anointed from
the fresh-seed sweep), rebuilds its VoteConfig + TradeConfig, and runs
every gate check that Helios can automate:

  1. Sharpe CI > 0 on TRAIN + VAL + HOLDOUT (block bootstrap 5000 boots)
  2a. Expectancy CI-low > 0 on TRAIN + VAL (v0.2.0 replaces old Gate 2)
  2b. Payoff-adjusted WR invariant (mean_r_net >= 0.05) on TRAIN + VAL
  3. Min 100 trades on TRAIN
  4. Walk-forward K=10 with ≥ 7 folds positive
  5. Max DD ≤ 15R on all three slices
  6. Permutation p-value ≤ 0.05 on all three slices (1000 shuffles)
  7. Shadow window: not checked here — separate operational gate

v0.2.0 amendment (2026-09-22): Gate 2 (WR ≥ 50%) was retired based on
51-seed evidence that asymmetric R:R is structural to oil's profitable
manifold. Replaced with Gate 2a + Gate 2b. Old WR field still reported
under `g2_wr_ge_50_retired` for continuity but not used in ship decisions.

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
from src.features.regime_labels import label_regimes
from src.sim.backtest import simulate
from src.sim.metrics import (block_bootstrap_expectancy,
                             block_bootstrap_sharpe, compute,
                             permutation_test)
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS

TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def _slice_report(joined: pd.DataFrame, tcfg, name: str, start: str, end: str,
                  regime_labels: pd.DataFrame | None = None) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades, reads_all=slc[["date", "read"]])
    boot = block_bootstrap_sharpe(trades, n_boot=5000, seed=1234)
    exp = block_bootstrap_expectancy(trades, n_boot=5000, seed=1234)
    perm = permutation_test(trades, n_perm=1000, seed=1234)
    by_regime = _breakdown_by_regime(trades, regime_labels)
    return {
        "slice": name, "start": start, "end": end,
        "metrics": asdict(m),
        "bootstrap_sharpe": boot,
        "bootstrap_expectancy": exp,
        "permutation": perm,
        "by_regime": by_regime,
    }


def _breakdown_by_regime(trades: pd.DataFrame,
                         regime_labels: pd.DataFrame | None) -> dict:
    """For each of bull/chop/bear, compute n_trades, WR, mean R.

    Assign each trade its regime based on the *entry_date* label. Trades
    whose entry-date regime is 'unknown' (pre-warmup) are excluded.
    """
    if trades.empty or regime_labels is None:
        return {"bull": None, "chop": None, "bear": None}
    lab = regime_labels[["date", "regime"]].copy()
    lab["date"] = pd.to_datetime(lab["date"])
    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    merged = t.merge(lab, left_on="entry_date", right_on="date", how="left")
    out: dict[str, dict | None] = {}
    for r in ("bull", "chop", "bear"):
        rows = merged[merged["regime"] == r]
        if len(rows) == 0:
            out[r] = None
            continue
        wins = (rows["r_net"] > 0).sum()
        out[r] = {
            "n_trades": int(len(rows)),
            "wr": float(wins / len(rows)),
            "mean_r_net": float(rows["r_net"].mean()),
            "total_r_net": float(rows["r_net"].sum()),
        }
    return out


def _pass(rep: dict) -> dict:
    m = rep["metrics"]
    return {
        "g1_sharpe_ci_pos": bool(rep["bootstrap_sharpe"]["ci_low"] > 0),
        # v0.2.0 Gate 2a: expectancy CI-low > 0
        "g2a_expectancy_ci_pos": bool(rep["bootstrap_expectancy"]["ci_low"] > 0),
        # v0.2.0 Gate 2b: WR*avg_R_up - (1-WR)*avg_R_down >= 0.05
        # Algebraically identical to mean_r_net >= 0.05 (see docs/PROTOCOL.md).
        "g2b_payoff_adjusted_wr": bool(m["mean_r_net"] >= 0.05),
        # v0.1.0 Gate 2 (WR >= 50%) retained as informational — RETIRED as a
        # ship gate per PROTOCOL v0.2.0 amendment (2026-09-22). Still reported
        # for continuity in historical audits and dashboards.
        "g2_wr_ge_50_retired": bool(m["directional_wr"] >= 0.50),
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

    # Precompute regime labels once — used by Gate B6 breakdown per slice.
    regime_labels = label_regimes(features)

    slices = [
        _slice_report(joined, trade_cfg, "TRAIN", *TRAIN,
                      regime_labels=regime_labels),
        _slice_report(joined, trade_cfg, "VALIDATION", *VAL,
                      regime_labels=regime_labels),
        _slice_report(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end,
                      regime_labels=regime_labels),
    ]

    # Walk-forward K=10 on 2006-2023 (spans TRAIN + VAL)
    wf_slice = features[(features["date"] >= pd.to_datetime("2006-01-01", utc=True))
                        & (features["date"] <= pd.to_datetime("2023-12-31", utc=True))].reset_index(drop=True)
    wf = walkforward(wf_slice, cfg_vote=vote_cfg, cfg_trade=trade_cfg, k=10)

    gates = {s["slice"]: _pass(s) for s in slices}
    gates["g4_walkforward_7of10"] = bool(wf["pass_7of10_rule"])

    # Gate B6: regime consistency. Combine TRAIN + VAL trades (skip HOLDOUT
    # to avoid leaking the audit slice into the decision), then require
    # each of bull/chop/bear to have positive mean R with at least 5 trades.
    combined = {}
    for r in ("bull", "chop", "bear"):
        agg_n = 0
        agg_r = 0.0
        for sname in ("TRAIN", "VALIDATION"):
            reg = next(s for s in slices if s["slice"] == sname)["by_regime"].get(r)
            if reg is None:
                continue
            agg_n += reg["n_trades"]
            agg_r += reg["total_r_net"]
        combined[r] = {
            "n_trades": agg_n,
            "mean_r_net": agg_r / agg_n if agg_n > 0 else None,
        }
    b6_pass = all(
        combined[r]["n_trades"] >= 5 and combined[r]["mean_r_net"] is not None
        and combined[r]["mean_r_net"] > 0
        for r in ("bull", "chop", "bear")
    )
    gates["b6_regime_consistency"] = bool(b6_pass)

    # Roll-up: strict PROTOCOL v0.2.0 (CANONICAL as of 2026-09-22)
    strict_v020_pass = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g2a_expectancy_ci_pos"]
        and gates["VALIDATION"]["g2a_expectancy_ci_pos"]
        and gates["TRAIN"]["g2b_payoff_adjusted_wr"]
        and gates["VALIDATION"]["g2b_payoff_adjusted_wr"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["VALIDATION"]["g5_maxdd_le_15r"]
        and gates["TRAIN"]["g6_perm_p_le_005"]
        and gates["g4_walkforward_7of10"]
    )
    # Retained for historical continuity; not used for ship decisions.
    strict_v010_pass_retired = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g2_wr_ge_50_retired"]
        and gates["VALIDATION"]["g2_wr_ge_50_retired"]
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
        "b6_regime_combined_train_val": combined,
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
        "strict_v020_pass": strict_v020_pass,
        "strict_v010_pass_retired": strict_v010_pass_retired,
        "protocol_version": "0.2.0",
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
              f"g1={g['g1_sharpe_ci_pos']} g2a={g['g2a_expectancy_ci_pos']} "
              f"g2b={g['g2b_payoff_adjusted_wr']} "
              f"g5={g['g5_maxdd_le_15r']} g6={g['g6_perm_p_le_005']}")
    print(f"WF: {wf['positive_expectancy_folds']}/10 positive-expectancy "
          f"({wf['positive_sharpe_folds']}/10 positive-Sharpe)  "
          f"g4={wf['pass_7of10_rule']}")
    print()
    print("B6 regime consistency (combined TRAIN+VAL):")
    for r in ("bull", "chop", "bear"):
        c = combined[r]
        mr = c["mean_r_net"]
        mr_s = f"{mr:+.3f}" if mr is not None else "  N/A"
        print(f"  {r:6s}: n={c['n_trades']:3d}  mean R = {mr_s}")
    print(f"  b6 pass: {b6_pass}")
    print()
    print(f"strict PROTOCOL v0.2.0 pass (canonical): {strict_v020_pass}")
    print(f"strict PROTOCOL v0.1.0 pass (RETIRED, informational only): {strict_v010_pass_retired}")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
