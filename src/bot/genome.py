"""HELIOS bot genome.

Genes encode both the engine's vote thresholds AND the trade-execution
parameters. The bot searches this joint space with a genetic algorithm on
TRAIN, then we validate on VALIDATION and HOLDOUT.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

import numpy as np

from src.engine.regime_vote import VoteConfig
from src.sim.backtest import TradeConfig


# (name, low, high, kind) — kind ∈ {"float", "int"}
GENE_SPEC: list[tuple[str, float, float, str]] = [
    # Vote weights
    ("w_trend", 0.5, 4.0, "float"),
    ("w_momentum", 0.5, 4.0, "float"),
    ("w_vol", 0.0, 3.0, "float"),
    ("w_curve", 0.5, 4.0, "float"),
    ("w_cot", 0.0, 4.0, "float"),
    ("w_eia", 0.0, 4.0, "float"),
    ("w_macro", 0.5, 4.0, "float"),
    # Thresholds
    ("trend_bull", 0.01, 0.10, "float"),
    ("trend_bear", -0.10, -0.01, "float"),
    ("momo_bull", 0.01, 0.10, "float"),
    ("momo_bear", -0.10, -0.01, "float"),
    ("cot_bull", -2.0, -0.5, "float"),  # extreme short = bullish
    ("cot_bear", 0.5, 2.5, "float"),
    ("curve_bull", 0.3, 2.0, "float"),
    ("curve_bear", -2.0, -0.3, "float"),
    ("dxy_bear", 0.01, 0.06, "float"),
    ("dxy_bull", -0.06, -0.01, "float"),
    # Discretization
    ("strong", 0.40, 0.80, "float"),
    ("moderate", 0.10, 0.40, "float"),
    ("min_coverage", 0.3, 0.8, "float"),
    # Trade geometry
    ("k_stop", 0.75, 2.5, "float"),
    ("k_target", 1.5, 5.0, "float"),
    ("max_hold_days", 5, 40, "int"),
]


def random_genome(rng: np.random.Generator) -> dict[str, float]:
    g: dict[str, float] = {}
    for name, lo, hi, kind in GENE_SPEC:
        v = rng.uniform(lo, hi)
        if kind == "int":
            v = int(round(v))
        g[name] = float(v)
    # Enforce strong > moderate
    if g["strong"] <= g["moderate"]:
        g["strong"] = g["moderate"] + 0.10
    return g


def clip(g: dict[str, float]) -> dict[str, float]:
    for name, lo, hi, kind in GENE_SPEC:
        v = g[name]
        v = min(max(v, lo), hi)
        if kind == "int":
            v = int(round(v))
        g[name] = float(v)
    if g["strong"] <= g["moderate"]:
        g["strong"] = g["moderate"] + 0.05
    return g


def genome_to_configs(g: dict[str, float]) -> tuple[VoteConfig, TradeConfig]:
    vote = VoteConfig(
        w_trend=g["w_trend"],
        w_momentum=g["w_momentum"],
        w_vol=g["w_vol"],
        w_curve=g["w_curve"],
        w_cot=g["w_cot"],
        w_eia=g["w_eia"],
        w_macro=g["w_macro"],
        trend_bull=g["trend_bull"],
        trend_bear=g["trend_bear"],
        momo_bull=g["momo_bull"],
        momo_bear=g["momo_bear"],
        cot_bull=g["cot_bull"],
        cot_bear=g["cot_bear"],
        curve_bull=g["curve_bull"],
        curve_bear=g["curve_bear"],
        dxy_bear=g["dxy_bear"],
        dxy_bull=g["dxy_bull"],
        strong=g["strong"],
        moderate=g["moderate"],
        min_coverage=g["min_coverage"],
    )
    trade = TradeConfig(
        k_stop=g["k_stop"],
        k_target=g["k_target"],
        max_hold_days=int(g["max_hold_days"]),
        daily_cadence=False,
    )
    return vote, trade


def uniform_crossover(a: dict[str, float], b: dict[str, float],
                      rng: np.random.Generator) -> dict[str, float]:
    child: dict[str, float] = {}
    for name, *_ in GENE_SPEC:
        child[name] = a[name] if rng.random() < 0.5 else b[name]
    return clip(child)


def mutate(g: dict[str, float], rng: np.random.Generator,
           sigma: float = 0.10) -> dict[str, float]:
    out = dict(g)
    for name, lo, hi, kind in GENE_SPEC:
        rng_bound = hi - lo
        out[name] = out[name] + rng.normal(0.0, sigma * rng_bound)
    return clip(out)
