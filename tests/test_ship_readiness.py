"""Smoke tests for scripts/ship_readiness.py.

Validates that the aggregator handles missing artifacts, computes the
readiness verdict correctly, and preserves the invariant that mean_r_net
is the payoff-adjusted-WR quantity Gate 2b evaluates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ship_readiness as sr


def test_load_returns_none_for_missing(tmp_path):
    assert sr._load(tmp_path / "nope.json") is None


def test_load_returns_error_for_malformed(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not: valid", encoding="utf-8")
    got = sr._load(p)
    assert got is not None and "__error__" in got


def test_fmt_bool_returns_pass_fail():
    assert sr._fmt(True) == "PASS"
    assert sr._fmt(False) == "FAIL"
    assert sr._fmt(None) == "  N/A"


def test_audit_row_extracts_all_gates():
    audit = {
        "strict_v010_pass": False,
        "proposed_v020_pass": True,
        "gates": {
            "TRAIN": {"g1_sharpe_ci_pos": True, "g2_wr_ge_50": False,
                      "g3_n_ge_100": True, "g5_maxdd_le_15r": True,
                      "g6_perm_p_le_005": True},
            "VALIDATION": {"g1_sharpe_ci_pos": True, "g2_wr_ge_50": False,
                            "g5_maxdd_le_15r": True, "g6_perm_p_le_005": True},
            "HOLDOUT": {"g1_sharpe_ci_pos": True, "g5_maxdd_le_15r": True,
                        "g6_perm_p_le_005": True},
            "g4_walkforward_7of10": True,
            "b6_regime_consistency": True,
        },
    }
    row = sr._audit_row(audit)
    assert row["TRAIN_g1_sharpe_ci_pos"] is True
    assert row["TRAIN_g2_wr_ge_50"] is False
    assert row["g4_wf_7of10"] is True
    assert row["strict_v010_pass"] is False
    assert row["proposed_v020_pass"] is True


def test_payoff_adjusted_invariant_uses_mean_r_net():
    """Gate 2b: WR*avg_up - (1-WR)*avg_down >= 0.05.

    Since mean_r_net = WR*avg_up - (1-WR)*avg_down algebraically, the
    invariant reduces to mean_r_net >= 0.05.
    """
    audit = {"slices": [
        {"slice": "TRAIN", "metrics": {"directional_wr": 0.38,
                                          "mean_r_net": 1.14}},
        {"slice": "VALIDATION", "metrics": {"directional_wr": 0.33,
                                              "mean_r_net": 0.88}},
        {"slice": "MARGINAL", "metrics": {"directional_wr": 0.50,
                                            "mean_r_net": 0.04}},
    ]}
    got = sr._payoff_adjusted_wr_invariant(audit)
    assert got["TRAIN"]["gate_2b_pass"] is True
    assert got["VALIDATION"]["gate_2b_pass"] is True
    assert got["MARGINAL"]["gate_2b_pass"] is False


def test_drift_summary_counts_negative_quarters():
    drift = {"quarters": [
        {"quarter": "2024Q1", "n_trades": 5, "wr": 0.4, "total_r_net": 5.0},
        {"quarter": "2024Q2", "n_trades": 3, "wr": 0.3, "total_r_net": -1.5},
        {"quarter": "2024Q3", "n_trades": 4, "wr": 0.5, "total_r_net": 2.0},
    ]}
    s = sr._drift_summary(drift)
    assert s["n_quarters"] == 3
    assert s["n_negative_quarters"] == 1
    assert s["total_r_holdout"] == 5.5
    assert s["worst_quarter"] == "2024Q2"


def test_drift_summary_handles_missing():
    assert sr._drift_summary(None)["status"] == "missing"


def test_cost_stress_all_positive_true_when_every_slice_positive():
    cs = {"scenarios": [
        {"cost_multiplier": 1.0, "slices": [
            {"slice": "TRAIN", "metrics": {"mean_r_net": 1.1}},
            {"slice": "VALIDATION", "metrics": {"mean_r_net": 0.9}},
            {"slice": "HOLDOUT", "metrics": {"mean_r_net": 0.8}},
        ]},
        {"cost_multiplier": 2.0, "slices": [
            {"slice": "TRAIN", "metrics": {"mean_r_net": 0.5}},
            {"slice": "VALIDATION", "metrics": {"mean_r_net": 0.3}},
            {"slice": "HOLDOUT", "metrics": {"mean_r_net": 0.2}},
        ]},
    ]}
    s = sr._cost_stress_summary(cs)
    assert s["status"] == "present"
    assert s["all_positive_all_slices"] is True


def test_cost_stress_flags_negative_slice():
    cs = {"scenarios": [{"cost_multiplier": 5.0, "slices": [
        {"slice": "TRAIN", "metrics": {"mean_r_net": 0.2}},
        {"slice": "VALIDATION", "metrics": {"mean_r_net": -0.1}},
        {"slice": "HOLDOUT", "metrics": {"mean_r_net": 0.1}},
    ]}]}
    s = sr._cost_stress_summary(cs)
    assert s["all_positive_all_slices"] is False


def test_verdict_green_light_only_when_no_blocking():
    audit_row = {"strict_v010_pass": False, "proposed_v020_pass": True}
    drift = {"status": "present"}
    cost = {"status": "present", "all_positive_all_slices": True}
    mc = {"status": "present", "prob_ruin": 0.0}
    shadow_ok = {"n_days": 30}
    shadow_short = {"n_days": 10}

    # Unsigned + short shadow → not green
    v = sr._readiness_verdict(audit_row, drift, cost, mc, shadow_short,
                                protocol_signed=False)
    assert v["ready_v020"] is True
    assert v["green_light"] is False

    # Signed + long shadow → green
    v = sr._readiness_verdict(audit_row, drift, cost, mc, shadow_ok,
                                protocol_signed=True)
    assert v["green_light"] is True
    assert v["blocking_reasons"] == []


def test_verdict_flags_high_ruin_prob():
    audit_row = {"strict_v010_pass": True, "proposed_v020_pass": True}
    drift = {"status": "present"}
    cost = {"status": "present", "all_positive_all_slices": True}
    mc = {"status": "present", "prob_ruin": 0.05}  # 5% ruin
    shadow = {"n_days": 30}
    v = sr._readiness_verdict(audit_row, drift, cost, mc, shadow,
                                protocol_signed=True)
    assert v["green_light"] is False
    assert any("ruin" in r.lower() for r in v["blocking_reasons"])


def test_sweep_evidence_summarizes_wr_pressure_failure():
    wrp = {"n_seeds": 10, "n_wr_pass_TRAIN": 0, "n_wr_pass_VAL": 0, "runs": []}
    got = sr._sweep_evidence(None, None, wrp)
    assert got["wr_pressure"]["n_seeds"] == 10
    assert "could not lift" in got["wr_pressure"]["verdict"]


def test_sweep_evidence_flags_wr_reachable_but_g1_fail():
    """WR gate reached but Gate 1 Sharpe CI-low fails on VAL — the real story."""
    wrp = {
        "n_seeds": 3, "n_wr_pass_TRAIN": 3, "n_wr_pass_VAL": 3,
        "runs": [
            {"slices": [
                {"slice": "TRAIN", "metrics": {"directional_wr": 0.65},
                 "bootstrap_sharpe": {"ci_low": 0.30}},
                {"slice": "VALIDATION", "metrics": {"directional_wr": 0.60},
                 "bootstrap_sharpe": {"ci_low": -0.40}},
            ]},
            {"slices": [
                {"slice": "TRAIN", "metrics": {"directional_wr": 0.60},
                 "bootstrap_sharpe": {"ci_low": 0.20}},
                {"slice": "VALIDATION", "metrics": {"directional_wr": 0.55},
                 "bootstrap_sharpe": {"ci_low": -0.20}},
            ]},
            {"slices": [
                {"slice": "TRAIN", "metrics": {"directional_wr": 0.58},
                 "bootstrap_sharpe": {"ci_low": 0.35}},
                {"slice": "VALIDATION", "metrics": {"directional_wr": 0.53},
                 "bootstrap_sharpe": {"ci_low": -0.10}},
            ]},
        ],
    }
    got = sr._sweep_evidence(None, None, wrp)
    wp = got["wr_pressure"]
    assert wp["n_wr_pass_VAL"] == 3
    assert wp["n_sharpe_ci_pass_VAL"] == 0
    assert wp["n_both_gates_pass_VAL"] == 0
    assert "no seed passes both" in wp["verdict"]


def test_sweep_evidence_flags_full_pass_if_any_seed_clears_both():
    wrp = {
        "n_seeds": 2, "n_wr_pass_TRAIN": 2, "n_wr_pass_VAL": 2,
        "runs": [
            {"slices": [
                {"slice": "TRAIN", "metrics": {"directional_wr": 0.60},
                 "bootstrap_sharpe": {"ci_low": 0.20}},
                {"slice": "VALIDATION", "metrics": {"directional_wr": 0.55},
                 "bootstrap_sharpe": {"ci_low": 0.30}},  # <== both pass!
            ]},
            {"slices": [
                {"slice": "TRAIN", "metrics": {"directional_wr": 0.58},
                 "bootstrap_sharpe": {"ci_low": 0.15}},
                {"slice": "VALIDATION", "metrics": {"directional_wr": 0.51},
                 "bootstrap_sharpe": {"ci_low": -0.05}},
            ]},
        ],
    }
    got = sr._sweep_evidence(None, None, wrp)
    wp = got["wr_pressure"]
    assert wp["n_both_gates_pass_VAL"] == 1
    assert "1 seed(s) pass both" in wp["verdict"]


def test_sweep_evidence_handles_all_missing():
    got = sr._sweep_evidence(None, None, None)
    assert got == {"fresh_seed": None, "engine_v02": None, "wr_pressure": None,
                    "alt_strategy": None}


def test_sweep_evidence_alt_strategy_asymmetric_family_stays_asymmetric():
    alts = {
        "n_seeds": 3,
        "pinned": {"w_trend": 0.5, "w_momentum": 0.5},
        "n_strict_v010_pass": 0,
        "runs": [
            {"trade_cfg": {"rr": 4.3},
             "slices": [{"slice": "VALIDATION",
                         "metrics": {"directional_wr": 0.40}}]},
            {"trade_cfg": {"rr": 5.1},
             "slices": [{"slice": "VALIDATION",
                         "metrics": {"directional_wr": 0.38}}]},
            {"trade_cfg": {"rr": 3.9},
             "slices": [{"slice": "VALIDATION",
                         "metrics": {"directional_wr": 0.35}}]},
        ],
    }
    got = sr._sweep_evidence(None, None, None, alts)
    a = got["alt_strategy"]
    assert a["n_symmetric_rr_lt_2"] == 0
    assert a["n_wr_pass_VAL"] == 0
    assert a["n_strict_v010_pass"] == 0
    assert "family stays asymmetric" in a["verdict"]


def test_sweep_evidence_alt_strategy_flags_strict_pass():
    alts = {
        "n_seeds": 2,
        "pinned": {"w_trend": 0.5, "w_momentum": 0.5},
        "n_strict_v010_pass": 1,
        "runs": [
            {"trade_cfg": {"rr": 1.0},
             "slices": [{"slice": "VALIDATION",
                         "metrics": {"directional_wr": 0.55}}]},
            {"trade_cfg": {"rr": 4.0},
             "slices": [{"slice": "VALIDATION",
                         "metrics": {"directional_wr": 0.40}}]},
        ],
    }
    got = sr._sweep_evidence(None, None, None, alts)
    a = got["alt_strategy"]
    assert a["n_symmetric_rr_lt_2"] == 1
    assert a["n_wr_pass_VAL"] == 1
    assert "pass strict v0.1.0" in a["verdict"]
