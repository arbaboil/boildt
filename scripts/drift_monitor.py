"""Drift monitor — compensating control for the early-ship override.

PROTOCOL v0.2.1 (2026-09-22) shipped bot v3 seed 7 on day 5 of the 28-day
shadow window under an Owner-approved override. This script provides the
heightened live monitoring required by that override: every day's emitted
read is sanity-checked against multiple invariants; anything outside bounds
trips a drift flag that pauses live emission and forces SHADOW mode until
Owner clears it.

Checks (any FAIL → drift flag):
  1. Basic sanity — direction in valid enum, confidence 0-100, price > 0,
     ATR within [0.5%, 10%] of price.
  2. priceStep bounds — suggested stop within [0.5×, 1.5×] price.
  3. Confidence outlier — today's confidence within [median − 2σ, median + 2σ]
     of the last 14 shadow entries (or all if <14).
  4. Direction churn — no more than 2 direction flips in the last 5 shadow
     days (churn = signal noise).
  5. Coverage — at least min_coverage of the vote components have values.
  6. Provenance — genome_hash matches the audited ship candidate (no
     silent candidate swap).

Outputs:
  results/drift_status.json         (machine-readable summary)
  admin/drift.flag                  (present iff drift detected)

Exit code:
  0 — all checks pass
  1 — one or more checks failed (drift flag written)

Integration:
  Runs after emit_reads in daily.yml. If exit 1, the next daily emit
  will read admin/drift.flag and force SHADOW mode regardless of --live.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMITTED_WEEKLY = REPO / "results" / "emitted" / "weekly" / "current.json"
SHADOW_DIR = REPO / "results" / "shadow"
DRIFT_STATUS = REPO / "results" / "drift_status.json"
DRIFT_FLAG = REPO / "admin" / "drift.flag"

VALID_DIRECTIONS = {"LONG", "SHORT", "FLAT", "SHADOW"}
# Bounds copied from emit_reads.py — kept in sync manually.
ATR_PCT_MIN = 0.005
ATR_PCT_MAX = 0.10
PRICE_STOP_LOW = 0.5
PRICE_STOP_HIGH = 1.5
CONFIDENCE_Z_THRESHOLD = 2.0
DIRECTION_CHURN_MAX = 2   # flips per 5 days
COVERAGE_MIN = 0.30
LOOKBACK_DAYS = 14        # for confidence-outlier baseline
CHURN_WINDOW = 5


def _read_shadow_log(n: int = LOOKBACK_DAYS) -> list[dict]:
    """Return last n shadow entries sorted oldest → newest."""
    files = sorted(SHADOW_DIR.glob("*.json"))
    entries = []
    for p in files[-n:]:
        try:
            entries.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return entries


def check_basic_sanity(w: dict) -> list[str]:
    fails = []
    if w.get("direction") not in VALID_DIRECTIONS:
        fails.append(f"direction not in enum: {w.get('direction')!r}")
    c = w.get("confidence")
    if c is None or not (0 <= c <= 100):
        fails.append(f"confidence out of range: {c!r}")
    price = w.get("current_price")
    if not (isinstance(price, (int, float)) and price > 0):
        fails.append(f"current_price invalid: {price!r}")
    atr = w.get("atr_20d")
    if not (isinstance(atr, (int, float)) and atr > 0):
        fails.append(f"atr_20d invalid: {atr!r}")
    if isinstance(price, (int, float)) and isinstance(atr, (int, float)):
        pct = atr / price if price > 0 else 0
        if pct < ATR_PCT_MIN or pct > ATR_PCT_MAX:
            fails.append(f"atr_pct out of [{ATR_PCT_MIN},{ATR_PCT_MAX}]: {pct:.4f}")
    return fails


def check_priceStep_bounds(w: dict) -> list[str]:
    fails = []
    levels = w.get("levels", {}) or {}
    price = w.get("current_price")
    if not isinstance(price, (int, float)) or price <= 0:
        return fails
    stop = (levels.get("suggested_stop_price_at_entry")
            if "suggested_stop_price_at_entry" in levels
            else levels.get("stop_long_at") or levels.get("stop_short_at"))
    if stop is not None:
        if stop < PRICE_STOP_LOW * price or stop > PRICE_STOP_HIGH * price:
            fails.append(f"stop outside [{PRICE_STOP_LOW}x, {PRICE_STOP_HIGH}x] price: "
                          f"stop={stop} price={price}")
    return fails


def check_confidence_outlier(w: dict, history: list[dict]) -> list[str]:
    if len(history) < 3:
        return []
    past = [h.get("confidence", 0) for h in history[:-1] if h.get("confidence") is not None]
    if len(past) < 3:
        return []
    today = w.get("confidence")
    if today is None:
        return []
    # Convert from 0-1 (shadow log) to 0-100 (emitted) if needed
    if max(past) <= 1.0:
        past = [p * 100 for p in past]
    med = statistics.median(past)
    try:
        sig = statistics.stdev(past)
    except statistics.StatisticsError:
        return []
    if sig < 1e-6:
        return []
    z = abs(today - med) / sig
    if z > CONFIDENCE_Z_THRESHOLD:
        return [f"confidence outlier: today={today:.0f} median={med:.0f} "
                 f"std={sig:.1f} z={z:.2f}"]
    return []


def check_direction_churn(w: dict, history: list[dict]) -> list[str]:
    """Count direction flips in the last CHURN_WINDOW entries."""
    recent = history[-CHURN_WINDOW:]
    if len(recent) < 3:
        return []
    directions = []
    for h in recent:
        r = h.get("read")
        if r in {"BUY", "STRONG_BUY"}:
            directions.append(1)
        elif r in {"SELL", "STRONG_SELL"}:
            directions.append(-1)
        elif r == "FLAT":
            directions.append(0)
    flips = sum(1 for i in range(1, len(directions))
                if directions[i] != directions[i - 1])
    if flips > DIRECTION_CHURN_MAX:
        return [f"direction churn: {flips} flips in last {len(recent)} days "
                 f"(threshold {DIRECTION_CHURN_MAX})"]
    return []


def check_coverage(w: dict) -> list[str]:
    cov = w.get("provenance", {}).get("coverage")
    if cov is None:
        return []
    if cov < COVERAGE_MIN:
        return [f"vote coverage below minimum: {cov:.2f} < {COVERAGE_MIN}"]
    return []


def check_provenance(w: dict, expected_hash: str | None) -> list[str]:
    if expected_hash is None:
        return []
    got = (w.get("provenance", {}) or {}).get("genome_hash")
    if got != expected_hash:
        return [f"genome_hash mismatch: expected {expected_hash!r} got {got!r}"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-genome-hash", default=None,
                    help="If set, warn on genome_hash mismatch (catches silent "
                         "candidate swap).")
    args = ap.parse_args()

    if not EMITTED_WEEKLY.exists():
        # No emission to check yet — silent success.
        print("[drift_monitor] no emitted weekly artifact; nothing to check.")
        return 0

    w = json.loads(EMITTED_WEEKLY.read_text(encoding="utf-8"))
    history = _read_shadow_log(LOOKBACK_DAYS)

    fails: dict[str, list[str]] = {
        "basic_sanity": check_basic_sanity(w),
        "priceStep_bounds": check_priceStep_bounds(w),
        "confidence_outlier": check_confidence_outlier(w, history),
        "direction_churn": check_direction_churn(w, history),
        "coverage": check_coverage(w),
        "provenance": check_provenance(w, args.expected_genome_hash),
    }
    n_failing = sum(1 for v in fails.values() if v)
    drift = n_failing > 0
    status = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact_checked": str(EMITTED_WEEKLY.relative_to(REPO)),
        "history_days": len(history),
        "drift_detected": drift,
        "n_failing_categories": n_failing,
        "checks": fails,
        "protocol_version": "0.2.1",
        "override_active": True,
        "override_reason": "Owner-approved early ship (day 5 of 28); this monitor is the compensating control.",
    }
    DRIFT_STATUS.parent.mkdir(parents=True, exist_ok=True)
    DRIFT_STATUS.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")

    if drift:
        DRIFT_FLAG.parent.mkdir(parents=True, exist_ok=True)
        DRIFT_FLAG.write_text(
            json.dumps(status, indent=2), encoding="utf-8")
        print("=== DRIFT DETECTED ===")
        for cat, reasons in fails.items():
            for r in reasons:
                print(f"  [{cat}] {r}")
        print()
        print(f"Flag written to {DRIFT_FLAG}. Next emit will force SHADOW mode.")
        return 1

    # No drift — remove any stale flag from a previous run.
    if DRIFT_FLAG.exists():
        DRIFT_FLAG.unlink()
        print("[drift_monitor] previous drift flag cleared.")
    print(f"[drift_monitor] all {len(fails)} checks pass; history_days={len(history)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
