"""Alternative-strategy GA sweep — pins w_trend + w_momentum to their
lower bound so the search is forced to find edge from curve, COT,
macro, EIA, and vol (mean-reversion + fundamentals family).

If a genome from this family passes strict PROTOCOL v0.1.0 (Sharpe CI
+ WR >= 50% + WF + max_dd + n), it's an orthogonal bot line that
ships WITHOUT needing PROTOCOL v0.2.0 amendment.

Fitness: worst-fold Calmar (same as fresh-seed sweep). No WR penalty
here — we want to see what the search finds naturally when trend/momentum
are constrained.

Usage:
    python scripts/alt_strategy_sweep.py --seeds 41-50 --workers 6
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
from src.bot.genome import GENE_SPEC, genome_to_configs
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import block_bootstrap_sharpe, compute
from src.sim.walkforward import walkforward
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


ALT_DIR = RESULTS_BOTS.parent / "alt_strategy"
TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"

# Pin trend + momentum to min bound (0.5)
PIN_W_TREND = 0.5
PIN_W_MOMENTUM = 0.5


def _pin_genome(g: dict[str, float]) -> dict[str, float]:
    """Force w_trend and w_momentum to their pinned values."""
    g = dict(g)
    g["w_trend"] = PIN_W_TREND
    g["w_momentum"] = PIN_W_MOMENTUM
    return g


def _slice_report(joined, tcfg, name, start, end):
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=2000, seed=1234)
    return {"slice": name, "metrics": asdict(m), "bootstrap_sharpe": boot}


def _run_one(seed: int) -> dict:
    """Custom evolve loop that pins w_trend + w_momentum every generation."""
    import numpy as np
    from src.bot.genome import (mutate, random_genome, uniform_crossover)
    from src.bot.evolve import evaluate, tournament_select
    from src.sim.walkforward import kfold_ranges

    t0 = time.time()
    features_all = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features_all["date"] = pd.to_datetime(features_all["date"])
    features_all = features_all.sort_values("date").reset_index(drop=True)
    features_train = features_all[
        (features_all["date"] >= pd.to_datetime(TRAIN[0], utc=True))
        & (features_all["date"] <= pd.to_datetime(TRAIN[1], utc=True))
    ].reset_index(drop=True)

    pop_size = 64
    n_gens = 30
    elite = 4
    tourn_k = 3
    sigma = 0.12

    rng = np.random.default_rng(seed)
    ranges = kfold_ranges(features_train["date"], k=5)

    pop = [_pin_genome(random_genome(rng)) for _ in range(pop_size)]
    fits = [-999.0] * pop_size
    reports = [{}] * pop_size
    best_ever = {"fitness": -999.0}

    for gen in range(n_gens):
        for i in range(pop_size):
            reports[i] = evaluate(pop[i], features_train, ranges)
            fits[i] = reports[i]["fitness"]
        order = np.argsort(fits)[::-1]
        best = order[0]
        if fits[best] > best_ever["fitness"]:
            best_ever = {"fitness": fits[best], "genome": dict(pop[best]),
                         "report": reports[best], "gen": gen}
        new_pop = [dict(pop[order[i]]) for i in range(elite)]
        while len(new_pop) < pop_size:
            a = tournament_select(pop, fits, rng, k=tourn_k)
            b = tournament_select(pop, fits, rng, k=tourn_k)
            child = uniform_crossover(a, b, rng)
            child = mutate(child, rng, sigma=sigma)
            child = _pin_genome(child)   # re-pin after mutation
            new_pop.append(child)
        pop = new_pop

    genome = best_ever["genome"]
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
        "pinned": {"w_trend": PIN_W_TREND, "w_momentum": PIN_W_MOMENTUM},
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
    }
    ALT_DIR.mkdir(parents=True, exist_ok=True)
    p = ALT_DIR / f"seed_{seed:03d}.json"
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
    ap.add_argument("--seeds", default="41-50")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    seeds = _parse_seeds(args.seeds)
    print(f"Alt-strategy sweep: seeds={seeds} workers={args.workers}  "
          f"pinned w_trend={PIN_W_TREND} w_momentum={PIN_W_MOMENTUM}")
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
    n_strict = 0
    for r in runs:
        tr = r["slices"][0]; va = r["slices"][1]; ho = r["slices"][2]
        strict = (tr["bootstrap_sharpe"]["ci_low"] > 0
                   and va["bootstrap_sharpe"]["ci_low"] > 0
                   and tr["metrics"]["directional_wr"] >= 0.50
                   and va["metrics"]["directional_wr"] >= 0.50
                   and tr["metrics"]["n_trades"] >= 100
                   and tr["metrics"]["max_dd_r"] <= 15
                   and va["metrics"]["max_dd_r"] <= 15
                   and ho["metrics"]["max_dd_r"] <= 15
                   and r["walkforward"]["pass_7of10_rule"])
        if strict:
            n_strict += 1
    print(f"\nSummary: {len(runs)} seeds  strict PROTOCOL v0.1.0 pass: {n_strict}/{len(runs)}")
    summary = {
        "n_seeds": len(runs),
        "pinned": {"w_trend": PIN_W_TREND, "w_momentum": PIN_W_MOMENTUM},
        "n_strict_v010_pass": n_strict,
        "runs": runs,
        "elapsed_s": round(time.time() - t0, 1),
    }
    p = RESULTS_BOTS / "alt_strategy_sweep.json"
    p.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
