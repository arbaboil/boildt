"""Ship-readiness dashboard for HELIOS bot v3 seed 7 (and future candidates).

Consolidates every audit artifact under `results/` into a single JSON
report plus a human-readable table. Used by Owner to make the PROTOCOL
v0.2.0 sign-off decision.

Sources aggregated:
  - Candidate audit (Gate 1-6 + B6, walk-forward, v0.1.0 vs v0.2.0 pass)
  - Cost stress (fee/slippage scenarios)
  - Holdout drift (quarterly WR + R breakdown)
  - Feature ablation (drop-one importance)
  - Monte Carlo (10k paths, ruin prob, expected R)
  - Shadow log status (files under results/shadow/)
  - Fresh-seed sweep evidence (0/20 pass WR)
  - Engine v0.2 sweep evidence (0/12 pass WR, symmetric R:R destroys VAL/HO)
  - WR-pressure sweep evidence (if present)

Output:
  results/ship_readiness.json — machine-readable
  stdout — human-readable table

Exit codes:
  0 = fully ready for PROTOCOL v0.2.0 shadow start
  1 = candidate audit missing
  2 = any critical gate hard-failed
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"__error__": f"{type(e).__name__}: {e}"}


def _fmt(x, spec="+.2f"):
    if x is None:
        return "  N/A"
    if isinstance(x, bool):
        return "PASS" if x else "FAIL"
    try:
        return format(x, spec)
    except Exception:
        return str(x)


def _audit_row(audit: dict) -> dict:
    gates = audit.get("gates", {})
    return {
        "TRAIN_g1_sharpe_ci_pos": gates.get("TRAIN", {}).get("g1_sharpe_ci_pos"),
        "VAL_g1_sharpe_ci_pos": gates.get("VALIDATION", {}).get("g1_sharpe_ci_pos"),
        "HO_g1_sharpe_ci_pos": gates.get("HOLDOUT", {}).get("g1_sharpe_ci_pos"),
        "TRAIN_g2_wr_ge_50": gates.get("TRAIN", {}).get("g2_wr_ge_50"),
        "VAL_g2_wr_ge_50": gates.get("VALIDATION", {}).get("g2_wr_ge_50"),
        "TRAIN_g3_n_ge_100": gates.get("TRAIN", {}).get("g3_n_ge_100"),
        "g4_wf_7of10": gates.get("g4_walkforward_7of10"),
        "TRAIN_g5_dd_le_15": gates.get("TRAIN", {}).get("g5_maxdd_le_15r"),
        "VAL_g5_dd_le_15": gates.get("VALIDATION", {}).get("g5_maxdd_le_15r"),
        "HO_g5_dd_le_15": gates.get("HOLDOUT", {}).get("g5_maxdd_le_15r"),
        "TRAIN_g6_perm_ok": gates.get("TRAIN", {}).get("g6_perm_p_le_005"),
        "VAL_g6_perm_ok": gates.get("VALIDATION", {}).get("g6_perm_p_le_005"),
        "HO_g6_perm_ok": gates.get("HOLDOUT", {}).get("g6_perm_p_le_005"),
        "b6_regime_ok": gates.get("b6_regime_consistency"),
        "strict_v010_pass": audit.get("strict_v010_pass"),
        "proposed_v020_pass": audit.get("proposed_v020_pass"),
    }


def _payoff_adjusted_wr_invariant(audit: dict) -> dict:
    """Gate 2b: WR * avg_R_up - (1-WR) * avg_R_down >= 0.05."""
    out = {}
    for s in audit.get("slices", []):
        m = s["metrics"]
        # Reconstruct avg_R_up / avg_R_down from targets/stops if available.
        # metrics doesn't carry per-side avg R, so compute from mean_r_net + WR.
        # For a hit-target/hit-stop model: avg_R_up ≈ k_target/k_stop, avg_R_down ≈ 1.
        # We approximate via the trade-cfg if given, but safer: use total_r and n.
        wr = m["directional_wr"]
        # Approximation: infer avg_up and avg_down from mean and WR
        # mean = WR * avg_up - (1-WR) * avg_down
        # Not solvable from one equation. Skip if we can't get it directly.
        # Use published gates: v0.2.0 gate 2b requires mean_r_net > 0.05 as
        # a proxy since we don't have avg_up/avg_down here.
        gate_2b = wr * 0 + m["mean_r_net"]  # simple: mean_r_net >= 0.05
        out[s["slice"]] = {
            "wr": wr,
            "mean_r_net": m["mean_r_net"],
            "gate_2b_pass": m["mean_r_net"] >= 0.05,
        }
    return out


def _drift_summary(drift: dict) -> dict:
    if drift is None:
        return {"status": "missing"}
    qs = drift.get("quarters", [])
    if not qs:
        return {"status": "empty"}
    n_neg = sum(1 for q in qs if q["total_r_net"] < 0)
    total_r = sum(q["total_r_net"] for q in qs)
    total_n = sum(q["n_trades"] for q in qs)
    return {
        "status": "present",
        "n_quarters": len(qs),
        "n_negative_quarters": n_neg,
        "total_r_holdout": round(total_r, 2),
        "total_n_holdout": total_n,
        "holdout_wr": round(sum((q["wr"] * q["n_trades"]) for q in qs) / total_n, 3)
                       if total_n > 0 else None,
        "worst_quarter": min(qs, key=lambda q: q["total_r_net"])["quarter"],
    }


def _cost_stress_summary(cs: dict) -> dict:
    if cs is None:
        return {"status": "missing"}
    scenarios = cs.get("scenarios", [])
    result = []
    for sc in scenarios:
        mult = sc.get("cost_multiplier") or sc.get("extra_slippage_bps", "n/a")
        train = next((s for s in sc.get("slices", []) if s["slice"] == "TRAIN"), None)
        val = next((s for s in sc.get("slices", []) if s["slice"] == "VALIDATION"), None)
        ho = next((s for s in sc.get("slices", []) if s["slice"] == "HOLDOUT"), None)
        result.append({
            "mult": mult,
            "TRAIN_mean_r": train["metrics"]["mean_r_net"] if train else None,
            "VAL_mean_r": val["metrics"]["mean_r_net"] if val else None,
            "HO_mean_r": ho["metrics"]["mean_r_net"] if ho else None,
        })
    all_positive = all(
        (r["TRAIN_mean_r"] or -1) > 0
        and (r["VAL_mean_r"] or -1) > 0
        and (r["HO_mean_r"] or -1) > 0
        for r in result
    )
    return {"status": "present", "scenarios": result, "all_positive_all_slices": all_positive}


def _monte_carlo_summary(mc: dict) -> dict:
    if mc is None:
        return {"status": "missing"}
    b = mc.get("baseline") or {}
    return {
        "status": "present",
        "horizon_trades": b.get("horizon_trades"),
        "n_paths": b.get("n_paths"),
        "prob_positive_final_r": b.get("prob_positive_final_r"),
        "prob_ruin": b.get("prob_ruin"),
        "final_r_median": b.get("final_r", {}).get("median"),
        "final_r_p05": b.get("final_r", {}).get("p05"),
        "max_dd_r_p95": b.get("max_dd_r", {}).get("p95"),
    }


def _shadow_status() -> dict:
    d = RESULTS / "shadow"
    if not d.exists():
        return {"status": "missing", "n_days": 0}
    files = sorted(f.name for f in d.glob("*.json"))
    return {
        "status": "present",
        "n_days": len(files),
        "first_day": files[0] if files else None,
        "last_day": files[-1] if files else None,
        "days_until_gate7_pass": max(0, 28 - len(files)),
    }


def _sweep_evidence(freshseed: dict | None, engine_v02: dict | None,
                    wr_pressure: dict | None,
                    alt_strategy: dict | None = None) -> dict:
    out = {"fresh_seed": None, "engine_v02": None, "wr_pressure": None,
           "alt_strategy": None}
    if freshseed is not None:
        s = freshseed.get("summary", {})
        out["fresh_seed"] = {
            "n_seeds": s.get("n_seeds"),
            "frac_wr_pass_TRAIN": s.get("frac_g2_pass_TRAIN"),
            "frac_gates_1_5_no_wr_strict": s.get("frac_gates_1_5_no_wr_strict"),
            "verdict": "0 seeds pass WR — asymmetric R:R inevitable"
                       if s.get("frac_g2_pass_TRAIN", 0) == 0 else "some pass",
        }
    if engine_v02 is not None:
        n_pass_ci_all = 0
        n_pass_wr = 0
        for r in engine_v02.get("runs", []):
            slices = r.get("slices", [])
            if len(slices) >= 3:
                ci_pass = all(sl["bootstrap_sharpe"]["ci_low"] > 0 for sl in slices[:3])
                wr_pass = all(sl["metrics"]["directional_wr"] >= 0.50 for sl in slices[:2])
                if ci_pass: n_pass_ci_all += 1
                if wr_pass: n_pass_wr += 1
        out["engine_v02"] = {
            "n_seeds": engine_v02.get("n_seeds"),
            "n_pass_wr_train_val": n_pass_wr,
            "n_pass_g1_all_slices": n_pass_ci_all,
            "verdict": "locked symmetric R:R destroys VAL/HOLDOUT generalization"
                       if n_pass_ci_all == 0 else "some pass",
        }
    if wr_pressure is not None:
        # Compute how many WR-pressure seeds also pass Gate 1 (Sharpe CI-low > 0)
        # on VAL — the true "strict v0.1.0 candidate" filter.
        n_g1_pass_val = 0
        n_both_g1_g2_val = 0
        for r in wr_pressure.get("runs", []):
            slices = r.get("slices", [])
            va = next((s for s in slices if s.get("slice") == "VALIDATION"), None)
            if va is None:
                continue
            g1 = va.get("bootstrap_sharpe", {}).get("ci_low", -1.0) > 0
            g2 = va.get("metrics", {}).get("directional_wr", 0) >= 0.50
            if g1:
                n_g1_pass_val += 1
            if g1 and g2:
                n_both_g1_g2_val += 1
        wr_val_pass = wr_pressure.get("n_wr_pass_VAL", 0)
        out["wr_pressure"] = {
            "n_seeds": wr_pressure.get("n_seeds"),
            "n_wr_pass_TRAIN": wr_pressure.get("n_wr_pass_TRAIN"),
            "n_wr_pass_VAL": wr_val_pass,
            "n_sharpe_ci_pass_VAL": n_g1_pass_val,
            "n_both_gates_pass_VAL": n_both_g1_g2_val,
            "verdict": (
                "WR gate reachable but no seed passes both Gate 1 and Gate 2 on VAL"
                if wr_val_pass > 0 and n_both_g1_g2_val == 0
                else ("WR-penalty fitness could not lift WR above 50%"
                      if wr_val_pass == 0
                      else f"{n_both_g1_g2_val} seed(s) pass both Gate 1+2 on VAL")
            ),
        }
    if alt_strategy is not None:
        # Count seeds whose RR is ~symmetric (< 2.0) as "escaped the
        # asymmetric family" — a lift-off from oil's default geometry.
        n_symmetric = 0
        n_wr_pass_val = 0
        n_strict_v010 = alt_strategy.get("n_strict_v010_pass", 0)
        for r in alt_strategy.get("runs", []):
            rr = r.get("trade_cfg", {}).get("rr", 0)
            if rr < 2.0:
                n_symmetric += 1
            va = next((s for s in r.get("slices", []) if s.get("slice") == "VALIDATION"), None)
            if va and va.get("metrics", {}).get("directional_wr", 0) >= 0.50:
                n_wr_pass_val += 1
        pinned = alt_strategy.get("pinned", {})
        out["alt_strategy"] = {
            "n_seeds": alt_strategy.get("n_seeds"),
            "pinned": pinned,
            "n_symmetric_rr_lt_2": n_symmetric,
            "n_wr_pass_VAL": n_wr_pass_val,
            "n_strict_v010_pass": n_strict_v010,
            "verdict": (
                "even with trend+momentum pinned low, family stays asymmetric-R:R"
                if n_symmetric == 0 and n_strict_v010 == 0
                else (f"{n_strict_v010} seed(s) pass strict v0.1.0"
                      if n_strict_v010 > 0
                      else f"{n_symmetric} seed(s) escaped asymmetric family but none pass v0.1.0")
            ),
        }
    return out


def _readiness_verdict(audit_row: dict, drift: dict, cost: dict,
                        mc: dict, shadow: dict, protocol_signed: bool) -> dict:
    """Compute overall ship-readiness."""
    reasons = []
    ready_v010 = audit_row.get("strict_v010_pass") is True
    ready_v020 = audit_row.get("proposed_v020_pass") is True
    if not ready_v010 and not ready_v020:
        reasons.append("candidate fails both v0.1.0 AND v0.2.0")
    if cost.get("status") == "present" and not cost.get("all_positive_all_slices"):
        reasons.append("cost stress: some scenario has negative mean R on a slice")
    if mc.get("status") == "present" and (mc.get("prob_ruin") or 0) > 0.01:
        reasons.append(f"Monte Carlo ruin prob > 1%: {mc.get('prob_ruin')}")
    if not protocol_signed:
        reasons.append("PROTOCOL v0.2.0 unsigned (Owner action required)")
    gate7_needed = max(0, 28 - shadow.get("n_days", 0))
    if gate7_needed > 0:
        reasons.append(f"Gate 7 shadow: {gate7_needed} days remaining "
                        f"({shadow.get('n_days', 0)}/28)")
    return {
        "ready_v010": ready_v010,
        "ready_v020": ready_v020,
        "blocking_reasons": reasons,
        "green_light": len(reasons) == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-stem", default="bot_v3_seed7_candidate")
    ap.add_argument("--protocol-signed", action="store_true",
                    help="Set once Owner signs PROTOCOL v0.2.0")
    ap.add_argument("--out", default=str(RESULTS / "ship_readiness.json"))
    args = ap.parse_args()

    stem = args.candidate_stem
    audit = _load(RESULTS / "bots" / f"{stem}_audit.json")
    if audit is None:
        print(f"[FATAL] audit missing: results/bots/{stem}_audit.json", file=sys.stderr)
        return 1

    cost = _load(RESULTS / "bots" / f"{stem}_cost_stress.json")
    drift = _load(RESULTS / "bots" / f"{stem}_holdout_drift.json")
    ablation = _load(RESULTS / "bots" / f"{stem}_ablation.json")
    mc = _load(RESULTS / "monte_carlo" / f"{stem}_mc.json")

    fresh = _load(RESULTS / "bots" / "bot_v2_freshseed_sweep.json")
    eng2 = _load(RESULTS / "bots" / "engine_v02_sweep.json")
    wrp = _load(RESULTS / "bots" / "wr_pressure_sweep.json")
    alts = _load(RESULTS / "bots" / "alt_strategy_sweep.json")
    sig_qual = _load(RESULTS / "engine_signal_quality.json")

    audit_row = _audit_row(audit)
    gate_2b = _payoff_adjusted_wr_invariant(audit)
    drift_sum = _drift_summary(drift)
    cost_sum = _cost_stress_summary(cost)
    mc_sum = _monte_carlo_summary(mc)
    shadow = _shadow_status()
    sweeps = _sweep_evidence(fresh, eng2, wrp, alts)

    verdict = _readiness_verdict(audit_row, drift_sum, cost_sum, mc_sum, shadow,
                                   protocol_signed=args.protocol_signed)

    # Engine-only ship-path signal quality (Plan B if v0.2.0 rejected).
    sig_qual_summary: dict | None = None
    if sig_qual is not None:
        sig_qual_summary = {"source": sig_qual.get("source")}
        for s in sig_qual.get("slices", []):
            sig_qual_summary[s["slice"]] = {
                "coverage": round(s["coverage"], 3),
                "stability": round(s["stability"], 3),
                "wr_5d": s["directional_accuracy_5d"].get("directional_wr"),
                "ic_5d": s["ic"].get("ic_5d", {}).get("ic"),
                "ic_20d": s["ic"].get("ic_20d", {}).get("ic"),
                # Engine-only gates E1-E4
                "e1_wr_ge_50": s["directional_accuracy_5d"].get("directional_wr", 0) >= 0.50
                                if s["directional_accuracy_5d"].get("directional_wr") is not None else None,
                "e2_ic5d_positive": (s["ic"].get("ic_5d", {}).get("ic") or -1) > 0,
                "e3_coverage_ge_30pct": s["coverage"] >= 0.30,
                "e4_stability_ge_70pct": s["stability"] >= 0.70,
            }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_stem": stem,
        "verdict": verdict,
        "gates": audit_row,
        "gate_2b_payoff_adjusted": gate_2b,
        "drift": drift_sum,
        "cost_stress": cost_sum,
        "monte_carlo": mc_sum,
        "shadow": shadow,
        "sweep_evidence": sweeps,
        "engine_only_signal_quality": sig_qual_summary,
        "sources": {
            "audit": str((RESULTS / "bots" / f"{stem}_audit.json").relative_to(REPO)),
            "cost_stress": str((RESULTS / "bots" / f"{stem}_cost_stress.json").relative_to(REPO)) if cost else None,
            "drift": str((RESULTS / "bots" / f"{stem}_holdout_drift.json").relative_to(REPO)) if drift else None,
            "ablation": str((RESULTS / "bots" / f"{stem}_ablation.json").relative_to(REPO)) if ablation else None,
            "monte_carlo": str((RESULTS / "monte_carlo" / f"{stem}_mc.json").relative_to(REPO)) if mc else None,
        },
    }

    Path(args.out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"=== HELIOS ship-readiness — {stem} ===")
    print(f"generated: {report['generated_at_utc']}")
    print()
    print("GATE MATRIX (bot candidate):")
    for k, v in audit_row.items():
        print(f"  {k:32s}  {_fmt(v)}")
    print()
    print("PROTOCOL v0.2.0 payoff-adjusted invariant (Gate 2b — mean_r_net >= 0.05):")
    for slice_name, g in gate_2b.items():
        print(f"  {slice_name:12s}  WR={g['wr']:.0%}  mean_R={g['mean_r_net']:+.3f}  "
              f"g2b={_fmt(g['gate_2b_pass'])}")
    print()
    print("HOLDOUT DRIFT:")
    for k, v in drift_sum.items():
        print(f"  {k:32s}  {v}")
    print()
    print("COST STRESS:")
    print(f"  status                          {cost_sum.get('status')}")
    if cost_sum.get("status") == "present":
        for s in cost_sum["scenarios"]:
            print(f"  mult={s['mult']:>5}  TRAIN={_fmt(s['TRAIN_mean_r'])}  "
                  f"VAL={_fmt(s['VAL_mean_r'])}  HO={_fmt(s['HO_mean_r'])}")
        print(f"  all_positive_all_slices         {_fmt(cost_sum['all_positive_all_slices'])}")
    print()
    print("MONTE CARLO (10k paths, ~1 year horizon):")
    for k, v in mc_sum.items():
        print(f"  {k:32s}  {v}")
    print()
    print("SHADOW LOG STATUS:")
    for k, v in shadow.items():
        print(f"  {k:32s}  {v}")
    print()
    print("SWEEP EVIDENCE (WR-gate reachability):")
    for name, s in sweeps.items():
        print(f"  {name}:")
        if s is None:
            print("    (not present)")
            continue
        for k, v in s.items():
            print(f"    {k:30s}  {v}")
    print()
    if sig_qual_summary is not None:
        print("ENGINE-ONLY SIGNAL QUALITY (Plan B if v0.2.0 rejected):")
        for slice_name in ("TRAIN", "VALIDATION", "HOLDOUT"):
            g = sig_qual_summary.get(slice_name)
            if g is None:
                continue
            print(f"  {slice_name:12s}  coverage={g['coverage']:.0%}  stability={g['stability']:.0%}  "
                  f"WR_5d={_fmt(g['wr_5d'], '.1%')}  ic_5d={_fmt(g['ic_5d'], '+.4f')}  "
                  f"ic_20d={_fmt(g['ic_20d'], '+.4f')}")
            print(f"    E1_wr50={_fmt(g['e1_wr_ge_50'])}  E2_ic>0={_fmt(g['e2_ic5d_positive'])}  "
                  f"E3_cov30={_fmt(g['e3_coverage_ge_30pct'])}  E4_stab70={_fmt(g['e4_stability_ge_70pct'])}")
        print()

    print("=== VERDICT ===")
    print(f"  ready_v010:    {_fmt(verdict['ready_v010'])}")
    print(f"  ready_v020:    {_fmt(verdict['ready_v020'])}")
    print(f"  green_light:   {_fmt(verdict['green_light'])}")
    if verdict["blocking_reasons"]:
        print("  blocking:")
        for r in verdict["blocking_reasons"]:
            print(f"    - {r}")
    print()
    print(f"Wrote {args.out}")
    return 0 if verdict["green_light"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
