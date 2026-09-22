"""Genetic algorithm loop for HELIOS bot.

Fitness = geometric mean of Calmar across TRAIN K-fold slices, penalized
by survival flag (0 if wiped out on any fold).
"""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from src.bot.genome import (GENE_SPEC, clip, genome_to_configs, mutate,
                             random_genome, uniform_crossover)
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.sim.metrics import compute
from src.sim.walkforward import kfold_ranges


SURVIVAL_MIN_R = -20.0     # max cumulative-R drawdown before "wiped out"
MIN_TRADES_PER_FOLD = 3    # if fold has < N trades, count fold as skipped
MIN_ACTIVE_FOLDS_FRAC = 0.8  # need trades in ≥ this fraction of folds
MIN_TRADES_TOTAL = 30      # aggregate trades required across folds
COVERAGE_PENALTY = 8.0     # subtracted per missing fold


def evaluate(genome: dict[str, float], features: pd.DataFrame,
             ranges: list[tuple[pd.Timestamp, pd.Timestamp]],
             wr_target: float = 0.0,
             wr_penalty_scale: float = 0.0,
             trade_cfg_override: Any = None) -> dict[str, Any]:
    """Evaluate a genome on K folds.

    Fitness variants:
    - Default (`wr_penalty_scale=0`): worst-fold Calmar. This is bot v2's
      fitness — geometry-agnostic, picks the best risk-adjusted return
      without regard to WR. Discovers asymmetric-R:R strategies.
    - v3 style (`wr_penalty_scale>0, wr_target~0.50`): worst-fold Calmar
      minus a penalty proportional to the min-across-folds WR shortfall
      below `wr_target`. Pushes evolution toward symmetric-R:R geometries
      that clear PROTOCOL gate 2.

    Trade config lock:
    - Default: derived from the genome (v3 seed 7 style — k_stop/k_target/
      max_hold_days part of search).
    - `trade_cfg_override`: replaces genome-derived TradeConfig with a
      fixed one. Used by engine-only tuning (v0.2) that locks
      k_stop=1.5, k_target=3.0, max_hold_days=20 (AXIS-shape) and
      searches only VoteConfig.
    """
    vote_cfg, trade_cfg = genome_to_configs(genome)
    if trade_cfg_override is not None:
        trade_cfg = trade_cfg_override
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(reads[["date", "read", "confidence", "score", "coverage"]],
                            on="date", how="left")
    calmars: list[float] = []
    total_trades = 0
    total_r = 0.0
    max_dd = 0.0
    fold_wr: list[float] = []
    survived = True
    for s, e in ranges:
        slc = joined[(joined["date"] >= s) & (joined["date"] <= e)].reset_index(drop=True)
        trades = simulate(slc, trade_cfg)
        if len(trades) < MIN_TRADES_PER_FOLD:
            continue
        m = compute(trades, reads_all=None)
        # Calmar = total_r / max_dd; if max_dd is 0 (all winners; unusual), cap at 5
        c = m.total_r_net / m.max_dd_r if m.max_dd_r > 0 else 5.0
        calmars.append(c)
        fold_wr.append(m.directional_wr)
        total_trades += m.n_trades
        total_r += m.total_r_net
        max_dd = max(max_dd, m.max_dd_r)
        if m.total_r_net < SURVIVAL_MIN_R:
            survived = False
    n_active = len(calmars)
    n_folds_total = len(ranges)
    if n_active == 0 or total_trades < MIN_TRADES_TOTAL:
        return {"fitness": -999.0, "calmars": [], "n_trades": total_trades,
                "total_r": total_r, "max_dd": max_dd, "survived": survived,
                "n_folds": n_active}
    if n_active / n_folds_total < MIN_ACTIVE_FOLDS_FRAC:
        return {"fitness": -500.0 - (n_folds_total - n_active) * COVERAGE_PENALTY,
                "calmars": calmars, "n_trades": total_trades,
                "total_r": total_r, "max_dd": max_dd, "survived": survived,
                "n_folds": n_active}
    # Fitness = worst-fold Calmar (harder to overfit than median), penalized
    # by missing folds and by wipeout.
    fitness = float(min(calmars))
    fitness -= COVERAGE_PENALTY * (n_folds_total - n_active)
    if not survived:
        fitness -= 5.0

    # Optional WR penalty (v3 fitness). Uses the worst-fold WR so a genome
    # can't hide behind a lucky-fold WR while others are 30%.
    wr_shortfall = 0.0
    if wr_penalty_scale > 0 and fold_wr:
        min_wr = min(fold_wr)
        wr_shortfall = max(0.0, wr_target - min_wr)
        fitness -= wr_penalty_scale * wr_shortfall

    return {
        "fitness": fitness,
        "calmars": calmars,
        "median_calmar": float(np.median(calmars)),
        "mean_calmar": float(np.mean(calmars)),
        "fold_wr": fold_wr,
        "min_fold_wr": float(min(fold_wr)) if fold_wr else 0.0,
        "wr_shortfall": float(wr_shortfall),
        "n_trades": total_trades,
        "total_r": total_r,
        "max_dd": max_dd,
        "survived": survived,
        "n_folds": len(calmars),
    }


def tournament_select(pop: list[dict], fits: list[float],
                       rng: np.random.Generator, k: int = 3) -> dict:
    idx = rng.integers(0, len(pop), size=k)
    best = max(idx, key=lambda i: fits[i])
    return pop[best]


def evolve(features: pd.DataFrame,
           k_folds: int = 5,
           pop_size: int = 64,
           n_gens: int = 30,
           elite: int = 4,
           tourn_k: int = 3,
           sigma: float = 0.10,
           seed: int = 42,
           wr_target: float = 0.0,
           wr_penalty_scale: float = 0.0,
           trade_cfg_override: Any = None,
           verbose: bool = True) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    ranges = kfold_ranges(features["date"], k=k_folds)

    pop = [random_genome(rng) for _ in range(pop_size)]
    fits: list[float] = [-999.0] * pop_size
    reports: list[dict[str, Any]] = [{}] * pop_size

    history: list[dict] = []
    best_ever = {"fitness": -999.0}
    t0 = time.time()

    for gen in range(n_gens):
        for i in range(pop_size):
            reports[i] = evaluate(pop[i], features, ranges,
                                  wr_target=wr_target,
                                  wr_penalty_scale=wr_penalty_scale,
                                  trade_cfg_override=trade_cfg_override)
            fits[i] = reports[i]["fitness"]
        order = np.argsort(fits)[::-1]
        best = order[0]
        if fits[best] > best_ever["fitness"]:
            best_ever = {"fitness": fits[best], "genome": dict(pop[best]),
                         "report": reports[best], "gen": gen}
        history.append({
            "gen": gen,
            "best_fitness": float(fits[best]),
            "median_fitness": float(np.median(fits)),
            "elapsed_s": round(time.time() - t0, 1),
            "best_genome_snapshot": dict(pop[best]),
            "best_report": reports[best],
        })
        if verbose:
            r = reports[best]
            print(f"gen {gen:2d}  best_fit={fits[best]:+.3f}  median_fit={np.median(fits):+.3f}  "
                  f"n_trades={r.get('n_trades', 0):3d} total_r={r.get('total_r', 0):+.1f} "
                  f"folds={r.get('n_folds', 0)} elapsed={round(time.time() - t0)}s")

        # Next generation
        new_pop: list[dict] = [dict(pop[order[i]]) for i in range(elite)]
        while len(new_pop) < pop_size:
            a = tournament_select(pop, fits, rng, k=tourn_k)
            b = tournament_select(pop, fits, rng, k=tourn_k)
            child = uniform_crossover(a, b, rng)
            child = mutate(child, rng, sigma=sigma)
            new_pop.append(child)
        pop = new_pop

    return {
        "best_ever": best_ever,
        "history": history,
        "n_gens": n_gens,
        "pop_size": pop_size,
        "seed": seed,
        "wr_target": wr_target,
        "wr_penalty_scale": wr_penalty_scale,
        "elapsed_s": round(time.time() - t0, 1),
    }
