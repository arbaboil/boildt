"""WR-pressure sweep — searches for high-WR genomes under strong
WR-shortfall penalty.

Fitness = worst-fold Calmar minus 15 × max(0, 0.55 - min_fold_WR).
Any genome must clear at least 55% min-fold WR to avoid a large penalty.
This actively pushes the GA away from asymmetric R:R.

If any seed finds a genome with WR >= 50% on TRAIN + VAL AND clears
other gates, we have an "Option A" candidate that satisfies PROTOCOL
v0.1.0 without an amendment. If not, the search space truly doesn't
contain a WR-passing oil strategy under the current votes.

Usage:
    python scripts/wr_pressure_sweep.py --seeds 21-30 --workers 6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.evolve import evolve
from src.bot.genome import genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import block_bootstrap_sharpe, compute
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


WR_DIR = RESULTS_BOTS.parent / "wr_pressure"
TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"

WR_TARGET = 0.55           # push above the 50% gate
WR_PENALTY_SCALE = 15.0    # 5pp shortfall = -0.75 fitness hit


def _slice_report(joined, tcfg, name, start, end):
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=2000, seed=1234)
    return {"slice": name, "metrics": asdict(m), "bootstrap_sharpe": boot}


def _run_one(seed: int) -> dict:
    t0 = time.time()
    features_all = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features_all["date"] = pd.to_datetime(features_all["date"])
    features_all = features_all.sort_values("date").reset_index(drop=True)
    features_train = features_all[
        (features_all["date"] >= pd.to_datetime(TRAIN[0], utc=True))
        & (features_all["date"] <= pd.to_datetime(TRAIN[1], utc=True))
    ].reset_index(drop=True)

    ga = evolve(features_train, k_folds=5, pop_size=64, n_gens=30,
                elite=4, sigma=0.12, seed=seed,
                wr_target=WR_TARGET, wr_penalty_scale=WR_PENALTY_SCALE,
                verbose=False)
    genome = ga["best_ever"]["genome"]
    vote_cfg, trade_cfg = genome_to_configs(genome)

    wf_slice = features_all[
        (features_all["date"] >= pd.to_datetime("2006-01-01", utc=True))
        & (features_all["date"] <= pd.to_datetime("2023-12-31", utc=True))
    ].reset_index(drop=True)
    wf = walkforward(wf_slice, cfg_vote=vote_cfg, cfg_trade=trade_cfg, k=10)

    reads = score_matrix(features_all, vote_cfg)
    joined = features_all.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    holdout_end = str(features_all["date"].max().date())
    slices = [
        _slice_report(joined, trade_cfg, "TRAIN", *TRAIN),
        _slice_report(joined, trade_cfg, "VALIDATION", *VAL),
        _slice_report(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]

    out = {
        "seed": seed,
        "elapsed_s": round(time.time() - t0, 1),
        "genome": genome,
        "trade_cfg": {"k_stop": trade_cfg.k_stop,
                      "k_target": trade_cfg.k_target,
                      "max_hold_days": trade_cfg.max_hold_days,
                      "rr": trade_cfg.k_target / trade_cfg.k_stop},
        "slices": slices,
        "walkforward": {
            "positive_expectancy_folds": wf["positive_expectancy_folds"],
            "pass_7of10_rule": wf["pass_7of10_rule"],
        },
        "wr_target": WR_TARGET,
        "wr_penalty_scale": WR_PENALTY_SCALE,
    }
    WR_DIR.mkdir(parents=True, exist_ok=True)
    p = WR_DIR / f"seed_{seed:03d}.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def _parse_seeds(spec):
    seeds = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        elif part.strip():
            seeds.append(int(part))
    return seeds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="21-30")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    seeds = _parse_seeds(args.seeds)
    print(f"WR-pressure sweep: seeds={seeds} workers={args.workers}  "
          f"wr_target={WR_TARGET}  penalty_scale={WR_PENALTY_SCALE}")
    runs = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_run_one, s): s for s in seeds}
        for f in as_completed(futures):
            s = futures[f]
            try:
                r = f.result()
                runs.append(r)
                tr = r["slices"][0]["metrics"]; va = r["slices"][1]["metrics"]
                b_tr = r["slices"][0]["bootstrap_sharpe"]; b_va = r["slices"][1]["bootstrap_sharpe"]
                print(f"[seed {s:3d}] {r['elapsed_s']:.0f}s "
                      f"TRAIN n={tr['n_trades']:3d} WR={tr['directional_wr']:.0%} "
                      f"S={tr['sharpe_per_trade']:+.2f} CI[{b_tr['ci_low']:+.2f}] "
                      f"VAL n={va['n_trades']:3d} WR={va['directional_wr']:.0%} "
                      f"S={va['sharpe_per_trade']:+.2f} CI[{b_va['ci_low']:+.2f}] "
                      f"RR={r['trade_cfg']['rr']:.2f} "
                      f"WF={r['walkforward']['positive_expectancy_folds']}/10")
            except Exception as e:
                print(f"[seed {s:3d}] FAILED: {e!r}")

    runs.sort(key=lambda r: r["seed"])
    n_wr_tr = sum(1 for r in runs if r["slices"][0]["metrics"]["directional_wr"] >= 0.50)
    n_wr_va = sum(1 for r in runs if r["slices"][1]["metrics"]["directional_wr"] >= 0.50)
    print(f"\nSummary: {len(runs)} seeds  WR>=50% TRAIN={n_wr_tr}  WR>=50% VAL={n_wr_va}")
    summary = {
        "n_seeds": len(runs),
        "wr_target": WR_TARGET,
        "wr_penalty_scale": WR_PENALTY_SCALE,
        "n_wr_pass_TRAIN": n_wr_tr,
        "n_wr_pass_VAL": n_wr_va,
        "runs": runs,
        "elapsed_s": round(time.time() - t0, 1),
    }
    p = RESULTS_BOTS / "wr_pressure_sweep.json"
    p.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
