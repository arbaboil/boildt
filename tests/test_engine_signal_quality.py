"""Unit tests for scripts/engine_signal_quality.py — signal quality
metrics used by the engine-only ship path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine_signal_quality as esq


def test_read_to_signed_confidence_maps_directions():
    df = pd.DataFrame({
        "read": ["BUY", "STRONG_BUY", "FLAT", "SELL", "STRONG_SELL"],
        "confidence": [0.3, 0.9, 0.5, 0.4, 0.8],
    })
    got = esq.read_to_signed_confidence(df).tolist()
    assert got == [+0.3, +0.9, 0.0, -0.4, -0.8]


def test_coverage_ignores_flat_only():
    df = pd.DataFrame({"read": ["BUY", "FLAT", "SELL", "FLAT", "FLAT"]})
    assert esq.compute_coverage(df) == pytest.approx(0.4)


def test_coverage_empty_returns_zero():
    df = pd.DataFrame({"read": []})
    assert esq.compute_coverage(df) == 0.0


def test_stability_perfect_when_all_same():
    df = pd.DataFrame({"read": ["BUY"] * 10})
    assert esq.compute_read_stability(df) == pytest.approx(1.0)


def test_stability_partial_when_reads_change():
    df = pd.DataFrame({"read": ["BUY", "BUY", "SELL", "SELL", "FLAT"]})
    # transitions: same, diff, same, diff → 2 same of 4 pairs
    assert esq.compute_read_stability(df) == pytest.approx(0.5)


def test_stability_singleton_returns_one():
    df = pd.DataFrame({"read": ["BUY"]})
    assert esq.compute_read_stability(df) == 1.0


def test_directional_accuracy_ignores_flat():
    reads = pd.DataFrame({"read": ["BUY", "FLAT", "SELL", "BUY", "SELL"]})
    fwd = pd.Series([0.02, 0.03, -0.01, 0.01, 0.02])
    # BUY  +0.02 → correct
    # SELL -0.01 → correct
    # BUY  +0.01 → correct
    # SELL +0.02 → wrong (short-positive)
    # → 3 correct of 4 directional → WR = 0.75
    got = esq.compute_directional_accuracy(reads, fwd)
    assert got["n_directional"] == 4
    assert got["directional_wr"] == pytest.approx(0.75)
    assert got["flat_rate"] == pytest.approx(0.2)


def test_directional_accuracy_no_directional_returns_none():
    reads = pd.DataFrame({"read": ["FLAT"] * 5})
    fwd = pd.Series([0.01, 0.02, -0.01, 0.03, 0.0])
    got = esq.compute_directional_accuracy(reads, fwd)
    assert got["n_directional"] == 0
    assert got["directional_wr"] is None
    assert got["flat_rate"] == 1.0


def test_ic_positive_when_signal_predicts_forward_return():
    # sc = fr + small noise → IC ≈ 1
    n = 200
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, n)
    sc = pd.Series(base + rng.normal(0, 0.05, n))
    fr = pd.Series(base + rng.normal(0, 0.05, n))
    got = esq.compute_ic(sc, fr)
    assert got["n"] == n
    assert got["ic"] is not None
    assert got["ic"] > 0.90


def test_ic_null_when_signal_unrelated():
    n = 200
    rng = np.random.default_rng(1)
    sc = pd.Series(rng.normal(0, 1, n))
    fr = pd.Series(rng.normal(0, 1, n))  # independent
    got = esq.compute_ic(sc, fr)
    assert abs(got["ic"]) < 0.15   # noise-level


def test_ic_returns_none_when_too_few_rows():
    sc = pd.Series([0.1, 0.2])
    fr = pd.Series([0.01, 0.02])
    got = esq.compute_ic(sc, fr)
    assert got["ic"] is None
    assert got["n"] == 2


def test_ic_drops_nan_pairs():
    n = 100
    rng = np.random.default_rng(2)
    sc = pd.Series(list(rng.normal(0, 1, n)) + [np.nan] * 10)
    fr = pd.Series(list(rng.normal(0, 1, n)) + list(rng.normal(0, 1, 10)))
    got = esq.compute_ic(sc, fr)
    assert got["n"] == n
