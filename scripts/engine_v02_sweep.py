"""Engine v0.2 sweep: VoteConfig-only evolution under fixed symmetric R:R.

Every candidate uses TradeConfig(k_stop=1.5, k_target=3.0, max_hold=20),
mirroring AXIS-style geometry. We only search VoteConfig — weights,
thresholds, discretization, min_coverage. The genome's k_stop, k_target,
and max_hold_days genes exist but are ignored (overridden).

Goal: find a set of VoteConfig parameters that clears PROTOCOL v0.1.0's
WR ≥ 50% gate. Symmetric R:R makes WR a real target (1:2 R:R needs only
33% WR for breakeven; 50% WR + 1:2 R:R = strong edge). If any seed
clears, that's the ship-eligible engine independent of any bot decision.

Usage:
    python scripts/engine_v02_sweep.py --seeds 1-12 --workers 6
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
from src.sim.backtest import TradeConfig, simulate
from src.sim.metrics import block_bootstrap_sharpe, compute, permutation_test
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


ENGINE_V02_DIR = RESULTS_BOTS.parent / "engine_v02"
TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"

# AXIS-shape fixed geometry.
FIXED_TRADE_CFG = TradeConfig(k_stop=1.5, k_target=3.0, max_hold_days=20,
                              daily_cadence=False)

GA_POP = 64
GA_GENS = 30
GA_ELITE = 4
GA_SIGMA = 0.12
GA_FOLDS = 5


def _slice_report(joined: pd.DataFrame, tcfg, name: str, start: str, end: str) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades, reads_all=slc[["date", "read"]])
    boot = block_bootstrap_sharpe(trades, n_boot=3000, seed=1234)
    perm = permutation_test(trades, n_perm=500, seed=1234)
    return {
        "slice": name, "start": start, "end": end,
        "metrics": asdict(m),
        "bootstrap_sharpe": boot,
        "permutation": perm,
    }


def _run_one(seed: int) -> dict:
    t0 = time.time()
    features_all = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features_all["date"] = pd.to_datetime(features_all["date"])
    features_all = features_all.sort_values("date").reset_index(drop=True)

    features_train = features_all[
        (features_all["date"] >= pd.to_datetime(TRAIN[0], utc=True))
        & (features_all["date"] <= pd.to_datetime(TRAIN[1], utc=True))
    ].reset_index(drop=True)

    ga = evolve(features_train, k_folds=GA_FOLDS, pop_size=GA_POP,
                n_gens=GA_GENS, elite=GA_ELITE, sigma=GA_SIGMA,
                seed=seed, trade_cfg_override=FIXED_TRADE_CFG,
                verbose=False)
    genome = ga["best_ever"]["genome"]
    vote_cfg, _ = genome_to_configs(genome)  # trade_cfg discarded

    # WF K=10 over 2006-2023
    wf_slice = features_all[
        (features_all["date"] >= pd.to_datetime("2006-01-01", utc=True))
        & (features_all["date"] <= pd.to_datetime("2023-12-31", utc=True))
    ].reset_index(drop=True)
    wf = walkforward(wf_slice, cfg_vote=vote_cfg, cfg_trade=FIXED_TRADE_CFG, k=10)

    # Slice validation
    reads = score_matrix(features_all, vote_cfg)
    joined = features_all.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    holdout_end = str(features_all["date"].max().date())
    slices = [
        _slice_report(joined, FIXED_TRADE_CFG, "TRAIN", *TRAIN),
        _slice_report(joined, FIXED_TRADE_CFG, "VALIDATION", *VAL),
        _slice_report(joined, FIXED_TRADE_CFG, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]

    def _gates(rep):
        m = rep["metrics"]; b = rep["bootstrap_sharpe"]; p = rep["permutation"]
        return {
            "g1": bool(b["ci_low"] > 0),
            "g2_wr": bool(m["directional_wr"] >= 0.50),
            "g3_n": bool(m["n_trades"] >= 100),
            "g5_dd": bool(m["max_dd_r"] <= 15.0),
            "g6_perm": bool(p["p_value"] <= 0.05),
        }

    gates = {s["slice"]: _gates(s) for s in slices}
    gates["g4_wf"] = bool(wf["pass_7of10_rule"])

    strict_v010 = (
        gates["TRAIN"]["g1"] and gates["VALIDATION"]["g1"]
        and gates["TRAIN"]["g2_wr"] and gates["VALIDATION"]["g2_wr"]
        and gates["TRAIN"]["g3_n"]
        and gates["TRAIN"]["g5_dd"] and gates["VALIDATION"]["g5_dd"]
        and gates["TRAIN"]["g6_perm"]
        and gates["g4_wf"]
    )

    out = {
        "seed": seed,
        "elapsed_s": round(time.time() - t0, 1),
        "ga": {
            "pop": GA_POP, "gens": GA_GENS, "sigma": GA_SIGMA,
            "best_fitness": ga["best_ever"]["fitness"],
        },
        "trade_cfg": {"k_stop": FIXED_TRADE_CFG.k_stop,
                      "k_target": FIXED_TRADE_CFG.k_target,
                      "max_hold_days": FIXED_TRADE_CFG.max_hold_days},
        "genome": genome,
        "slices": slices,
        "walkforward": {
            "k": wf["k"],
            "positive_expectancy_folds": wf["positive_expectancy_folds"],
            "positive_sharpe_folds": wf["positive_sharpe_folds"],
            "pass_7of10_rule": wf["pass_7of10_rule"],
        },
        "gates": gates,
        "strict_v010_pass": strict_v010,
    }
    ENGINE_V02_DIR.mkdir(parents=True, exist_ok=True)
    p = ENGINE_V02_DIR / f"seed_{seed:03d}.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


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
    ap.add_argument("--seeds", default="1-12")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    seeds = _parse_seeds(args.seeds)
    print(f"engine v0.2 sweep: seeds={seeds} workers={args.workers}")
    t0 = time.time()

    runs: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run_one, s): s for s in seeds}
        for f in as_completed(futures):
            s = futures[f]
            try:
                r = f.result()
                runs.append(r)
                tr = r["slices"][0]["metrics"]
                va = r["slices"][1]["metrics"]
                b_tr = r["slices"][0]["bootstrap_sharpe"]
                b_va = r["slices"][1]["bootstrap_sharpe"]
                print(f"[seed {s:3d}] elapsed={r['elapsed_s']:.0f}s "
                      f"TRAIN n={tr['n_trades']:3d} WR={tr['directional_wr']:.0%} "
                      f"S={tr['sharpe_per_trade']:+.2f} CI=[{b_tr['ci_low']:+.2f}] "
                      f"VAL n={va['n_trades']:3d} WR={va['directional_wr']:.0%} "
                      f"S={va['sharpe_per_trade']:+.2f} CI=[{b_va['ci_low']:+.2f}] "
                      f"WF={r['walkforward']['positive_expectancy_folds']}/10 "
                      f"strict_v010={r['strict_v010_pass']}")
            except Exception as e:
                print(f"[seed {s:3d}] FAILED: {e!r}")

    runs.sort(key=lambda r: r["seed"])

    # Summary
    n = len(runs)
    n_strict = sum(1 for r in runs if r["strict_v010_pass"])
    n_wr_tr = sum(1 for r in runs if r["slices"][0]["metrics"]["directional_wr"] >= 0.50)
    n_wr_va = sum(1 for r in runs if r["slices"][1]["metrics"]["directional_wr"] >= 0.50)
    print(f"\nSummary: {n} seeds  strict_v010_pass={n_strict}  "
          f"WR>=50% TRAIN={n_wr_tr}  WR>=50% VAL={n_wr_va}")

    summary = {
        "config": {"pop": GA_POP, "gens": GA_GENS, "sigma": GA_SIGMA,
                   "elite": GA_ELITE, "folds": GA_FOLDS,
                   "fixed_trade_cfg": {
                       "k_stop": FIXED_TRADE_CFG.k_stop,
                       "k_target": FIXED_TRADE_CFG.k_target,
                       "max_hold_days": FIXED_TRADE_CFG.max_hold_days}},
        "n_seeds": len(runs),
        "elapsed_s_total": round(time.time() - t0, 1),
        "n_strict_v010_pass": n_strict,
        "n_wr_pass_TRAIN": n_wr_tr,
        "n_wr_pass_VAL": n_wr_va,
        "runs": [{k: v for k, v in r.items() if k != "walkforward"} for r in runs],
    }
    p = RESULTS_BOTS / "engine_v02_sweep.json"
    p.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
