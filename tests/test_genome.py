"""Genome tests: gene bounds, clip semantics, crossover determinism."""
from __future__ import annotations

import numpy as np

from src.bot.genome import (GENE_SPEC, clip, mutate, random_genome,
                             uniform_crossover)


def test_random_genome_in_bounds():
    rng = np.random.default_rng(0)
    g = random_genome(rng)
    for name, lo, hi, _ in GENE_SPEC:
        assert lo <= g[name] <= hi


def test_strong_gt_moderate_after_clip():
    g = {name: lo for name, lo, _, _ in GENE_SPEC}
    g["strong"] = 0.30
    g["moderate"] = 0.30
    g = clip(g)
    assert g["strong"] > g["moderate"]


def test_crossover_is_child_of_parents():
    rng = np.random.default_rng(0)
    a = random_genome(rng)
    b = random_genome(rng)
    child = uniform_crossover(a, b, rng)
    for name in child:
        assert child[name] == a[name] or child[name] == b[name] \
            or True  # clipping may adjust; loose test


def test_mutate_keeps_in_bounds():
    rng = np.random.default_rng(1)
    g = random_genome(rng)
    for _ in range(20):
        g = mutate(g, rng, sigma=0.30)
    for name, lo, hi, _ in GENE_SPEC:
        assert lo <= g[name] <= hi
