"""Fresh-seed retest per PROTOCOL gate B7.

For each seed in the sweep:
  1. Evolve a bot from scratch with that seed (same GA config as bot_v2).
  2. Run K=10 walk-forward on the evolved genome (2006-2023).
  3. Run TRAIN/VAL/HOLDOUT slice validation on the evolved genome.
  4. Record: genome, gate 1-6 pass/fail per slice, walk-forward pass, evolved-
     fitness, and per-slice summary metrics.

Then aggregate: what fraction of seeds pass gate 1 (Sharpe CI>0), gate 2
(WR>=50%), gate 3 (n>=100 TRAIN trades), gate 4 (>=7/10 folds), gate 5
(max_dd<=15R). Report median metrics across seeds.

Runs seeds in parallel using ProcessPoolExecutor. Writes a single summary
JSON per seed under results/bots/freshseed/, and a combined roll-up at
results/bots/bot_v2_freshseed_sweep.json.

Usage:
  python scripts/freshseed_sweep.py --seeds 1-20 --workers 8

Cost: ~10 min per seed sequentially; with 8 workers, ~30 min for 20 seeds.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.evolve import evolve
from src.bot.genome import genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import block_bootstrap_sharpe, compute
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


FRESHSEED_DIR = RESULTS_BOTS / "freshseed"
TRAIN_RANGE = ("2006-01-01", "2018-12-31")
VAL_RANGE = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"

# Same GA config that produced bot_v2 (seed 42 baseline).
GA_POP = 64
GA_GENS = 30
GA_ELITE = 4
GA_SIGMA = 0.12
GA_FOLDS = 5


def _load_features() -> pd.DataFrame:
    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    return features.sort_values("date").reset_index(drop=True)


def _slice(features: pd.DataFrame, start: str, end: str | None = None) -> pd.DataFrame:
    lo = pd.to_datetime(start, utc=True)
    if end is None:
        return features[features["date"] >= lo].reset_index(drop=True)
    hi = pd.to_datetime(end, utc=True)
    return features[(features["date"] >= lo) & (features["date"] <= hi)].reset_index(drop=True)


def _slice_report(joined: pd.DataFrame, tcfg, name: str, start: str, end: str) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades, reads_all=slc[["date", "read"]])
    boot = block_bootstrap_sharpe(trades, n_boot=2000, seed=1234)
    return {
        "slice": name,
        "start": start,
        "end": end,
        "metrics": asdict(m),
        "bootstrap_sharpe": boot,
    }


def _run_one(seed: int) -> dict:
    t0 = time.time()
    features_all = _load_features()
    features_train = _slice(features_all, *TRAIN_RANGE)

    # --- 1. Evolve
    ga = evolve(
        features_train,
        k_folds=GA_FOLDS,
        pop_size=GA_POP,
        n_gens=GA_GENS,
        elite=GA_ELITE,
        sigma=GA_SIGMA,
        seed=seed,
        verbose=False,
    )
    genome = ga["best_ever"]["genome"]
    vote_cfg, trade_cfg = genome_to_configs(genome)

    # --- 2. Walk-forward K=10 across 2006..2023
    wf_slice = _slice(features_all, "2006-01-01", "2023-12-31")
    wf = walkforward(wf_slice, cfg_vote=vote_cfg, cfg_trade=trade_cfg, k=10, seed=seed)

    # --- 3. Slice validation
    reads = score_matrix(features_all, vote_cfg)
    joined = features_all.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    holdout_end = str(features_all["date"].max().date())
    slice_reports = [
        _slice_report(joined, trade_cfg, "TRAIN", TRAIN_RANGE[0], TRAIN_RANGE[1]),
        _slice_report(joined, trade_cfg, "VALIDATION", VAL_RANGE[0], VAL_RANGE[1]),
        _slice_report(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]

    # --- 4. Gate pass/fail (per PROTOCOL v0.1.0 gates 1-5)
    train = slice_reports[0]
    val = slice_reports[1]
    holdout = slice_reports[2]

    def gate_pass(rep):
        m = rep["metrics"]
        b = rep["bootstrap_sharpe"]
        return {
            "g1_sharpe_ci_pos": bool(b["ci_low"] > 0),
            "g2_wr_ge_50": bool(m["directional_wr"] >= 0.50),
            "g3_n_ge_100": bool(m["n_trades"] >= 100),
            "g5_maxdd_le_15r": bool(m["max_dd_r"] <= 15.0),
        }

    gates = {
        "TRAIN": gate_pass(train),
        "VALIDATION": gate_pass(val),
        "HOLDOUT": gate_pass(holdout),
        "g4_walkforward_7of10": bool(wf["pass_7of10_rule"]),
    }
    # Strict PROTOCOL v0.1.0: gates must be TRUE on TRAIN + VALIDATION + WF.
    # (g3 sample-count applies to in-sample only; not required on VAL.)
    all_gates_1_5 = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g2_wr_ge_50"]
        and gates["VALIDATION"]["g2_wr_ge_50"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["VALIDATION"]["g5_maxdd_le_15r"]
        and gates["g4_walkforward_7of10"]
    )
    # Diagnostic: strict protocol minus the WR gate — is WR the *only* thing
    # blocking most seeds?
    gates_1_5_no_wr = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["VALIDATION"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["VALIDATION"]["g5_maxdd_le_15r"]
        and gates["g4_walkforward_7of10"]
    )
    # TRAIN-only variant (loose) — historical comparison to session-1 note.
    gates_train_only = (
        gates["TRAIN"]["g1_sharpe_ci_pos"]
        and gates["TRAIN"]["g2_wr_ge_50"]
        and gates["TRAIN"]["g3_n_ge_100"]
        and gates["TRAIN"]["g5_maxdd_le_15r"]
        and gates["g4_walkforward_7of10"]
    )

    elapsed = round(time.time() - t0, 1)
    out = {
        "seed": seed,
        "elapsed_s": elapsed,
        "ga": {
            "pop": GA_POP, "gens": GA_GENS, "sigma": GA_SIGMA,
            "elite": GA_ELITE, "folds": GA_FOLDS,
            "best_fitness": ga["best_ever"]["fitness"],
            "best_report": ga["best_ever"]["report"],
        },
        "genome": genome,
        "slices": slice_reports,
        "walkforward": {
            "k": wf["k"],
            "positive_expectancy_folds": wf["positive_expectancy_folds"],
            "positive_sharpe_folds": wf["positive_sharpe_folds"],
            "pass_7of10_rule": wf["pass_7of10_rule"],
            "folds": [
                {"fold": f["fold"], "start": f["start"], "end": f["end"],
                 "n_trades": f["metrics"]["n_trades"],
                 "wr": f["metrics"]["directional_wr"],
                 "mean_r_net": f["metrics"]["mean_r_net"],
                 "sharpe_per_trade": f["metrics"]["sharpe_per_trade"],
                 "ci_low": f["bootstrap_sharpe"]["ci_low"],
                 "ci_high": f["bootstrap_sharpe"]["ci_high"]}
                for f in wf["folds"]
            ],
        },
        "gates": gates,
        "all_gates_1_5_pass": all_gates_1_5,
        "gates_1_5_no_wr_pass": gates_1_5_no_wr,
        "gates_train_only_pass": gates_train_only,
    }

    FRESHSEED_DIR.mkdir(parents=True, exist_ok=True)
    p = FRESHSEED_DIR / f"seed_{seed:03d}.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def _summarize(runs: list[dict]) -> dict:
    def get(rep, name, metric):
        for s in rep["slices"]:
            if s["slice"] == name:
                return s["metrics"][metric]
        return None

    def getci(rep, name, key):
        for s in rep["slices"]:
            if s["slice"] == name:
                return s["bootstrap_sharpe"][key]
        return None

    keys = [("TRAIN", "sharpe_per_trade"), ("VALIDATION", "sharpe_per_trade"),
            ("HOLDOUT", "sharpe_per_trade"),
            ("TRAIN", "directional_wr"), ("VALIDATION", "directional_wr"),
            ("HOLDOUT", "directional_wr"),
            ("TRAIN", "mean_r_net"), ("VALIDATION", "mean_r_net"),
            ("HOLDOUT", "mean_r_net"),
            ("TRAIN", "n_trades"), ("VALIDATION", "n_trades"),
            ("HOLDOUT", "n_trades")]
    summary = {}
    for slice_name, metric in keys:
        vals = [get(r, slice_name, metric) for r in runs]
        vals = [v for v in vals if v is not None]
        summary[f"{slice_name}_{metric}_median"] = float(np.median(vals))
        summary[f"{slice_name}_{metric}_p25"] = float(np.percentile(vals, 25))
        summary[f"{slice_name}_{metric}_p75"] = float(np.percentile(vals, 75))

    for slice_name in ("TRAIN", "VALIDATION", "HOLDOUT"):
        ci_lows = [getci(r, slice_name, "ci_low") for r in runs]
        summary[f"{slice_name}_sharpe_ci_low_median"] = float(np.median(ci_lows))

    # Gate pass rates
    n = len(runs)
    summary["n_seeds"] = n
    summary["frac_g1_pass_TRAIN"] = sum(r["gates"]["TRAIN"]["g1_sharpe_ci_pos"] for r in runs) / n
    summary["frac_g2_pass_TRAIN"] = sum(r["gates"]["TRAIN"]["g2_wr_ge_50"] for r in runs) / n
    summary["frac_g3_pass_TRAIN"] = sum(r["gates"]["TRAIN"]["g3_n_ge_100"] for r in runs) / n
    summary["frac_g4_wf_pass"] = sum(r["gates"]["g4_walkforward_7of10"] for r in runs) / n
    summary["frac_g5_pass_TRAIN"] = sum(r["gates"]["TRAIN"]["g5_maxdd_le_15r"] for r in runs) / n
    summary["frac_all_gates_1_5_strict"] = sum(r["all_gates_1_5_pass"] for r in runs) / n
    summary["frac_gates_1_5_no_wr_strict"] = sum(r["gates_1_5_no_wr_pass"] for r in runs) / n
    summary["frac_gates_train_only_pass"] = sum(r["gates_train_only_pass"] for r in runs) / n
    summary["frac_g2_pass_VALIDATION"] = sum(r["gates"]["VALIDATION"]["g2_wr_ge_50"] for r in runs) / n
    summary["frac_g1_pass_HOLDOUT"] = sum(r["gates"]["HOLDOUT"]["g1_sharpe_ci_pos"] for r in runs) / n
    summary["frac_g2_pass_HOLDOUT"] = sum(r["gates"]["HOLDOUT"]["g2_wr_ge_50"] for r in runs) / n
    return summary


def _parse_seeds(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20",
                    help="range/list like '1-20' or '1,3,5,42'")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="bot_v2_freshseed_sweep.json")
    args = ap.parse_args()

    seeds = _parse_seeds(args.seeds)
    print(f"Fresh-seed sweep: seeds={seeds} workers={args.workers}")
    t0 = time.time()

    runs: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run_one, s): s for s in seeds}
        for f in as_completed(futures):
            s = futures[f]
            try:
                r = f.result()
                runs.append(r)
                g = r["gates"]["TRAIN"]
                print(f"[seed {s:3d}] elapsed={r['elapsed_s']:.0f}s "
                      f"train_n={r['slices'][0]['metrics']['n_trades']:3d} "
                      f"train_wr={r['slices'][0]['metrics']['directional_wr']:.0%} "
                      f"train_sharpe={r['slices'][0]['metrics']['sharpe_per_trade']:+.2f} "
                      f"val_wr={r['slices'][1]['metrics']['directional_wr']:.0%} "
                      f"wf={r['walkforward']['positive_expectancy_folds']}/10 "
                      f"strict={r['all_gates_1_5_pass']} "
                      f"no_wr={r['gates_1_5_no_wr_pass']}")
            except Exception as e:
                print(f"[seed {s:3d}] FAILED: {e!r}")

    runs.sort(key=lambda r: r["seed"])
    summary = _summarize(runs)
    total_elapsed = round(time.time() - t0, 1)
    out = {
        "config": {"pop": GA_POP, "gens": GA_GENS, "sigma": GA_SIGMA,
                   "elite": GA_ELITE, "folds": GA_FOLDS,
                   "train_range": TRAIN_RANGE,
                   "val_range": VAL_RANGE,
                   "holdout_start": HOLDOUT_START},
        "n_seeds": len(runs),
        "elapsed_s_total": total_elapsed,
        "summary": summary,
        "runs": [{k: v for k, v in r.items() if k != "walkforward"} for r in runs],
        "walkforward_by_seed": {r["seed"]: r["walkforward"] for r in runs},
    }
    p = RESULTS_BOTS / args.out
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {p}")
    print(f"Total elapsed: {total_elapsed}s across {len(runs)} seeds")
    print(f"gate-1 (Sharpe CI>0) pass rate on TRAIN:  {summary['frac_g1_pass_TRAIN']:.0%}")
    print(f"gate-2 (WR>=50%)     pass rate on TRAIN:  {summary['frac_g2_pass_TRAIN']:.0%}")
    print(f"gate-3 (n>=100)      pass rate on TRAIN:  {summary['frac_g3_pass_TRAIN']:.0%}")
    print(f"gate-4 (WF 7/10)     pass rate:           {summary['frac_g4_wf_pass']:.0%}")
    print(f"gate-5 (DD<=15R)     pass rate on TRAIN:  {summary['frac_g5_pass_TRAIN']:.0%}")
    print(f"gate-2 (WR>=50%)     pass rate on VAL:    {summary['frac_g2_pass_VALIDATION']:.0%}")
    print(f"strict gates 1-5   (TRAIN+VAL+WF):        {summary['frac_all_gates_1_5_strict']:.0%}")
    print(f"strict minus WR   (TRAIN+VAL+WF, no WR):  {summary['frac_gates_1_5_no_wr_strict']:.0%}")
    print(f"loose gates 1-5    (TRAIN only, session-1 shape): {summary['frac_gates_train_only_pass']:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
