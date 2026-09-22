"""One-command daily pipeline for owner's cron.

Sequence:
  1. Pull fresh data (FRED + Yahoo + COT + Baker Hughes + EIA; skip Stooq
     due to its JS challenge). EIA pulled when EIA_API_KEY is set in .env.
  2. Rebuild features
  3. Log a candidate-shadow entry (if a candidate is configured) plus
     an untuned-engine trace
  4. Emit contract-shaped weekly + daily + backtest artifacts

Idempotent: safe to re-run in the same day. Skips pull if you pass
`--skip-pull` (useful for testing / re-emit after config changes).

Exit codes:
  0 success
  1 data pull failed for a critical source (WTI close missing)
  2 features build failed
  3 shadow write failed
  4 emit failed
  Non-zero exit is meaningful for cron / monitoring.

Usage:
  python scripts/daily_pipeline.py                                     # untuned
  python scripts/daily_pipeline.py --candidate results/bots/bot_v3_seed7_candidate.json
  python scripts/daily_pipeline.py --candidate ... --live              # ship mode
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], desc: str) -> int:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {desc}")
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=REPO, capture_output=False)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None,
                    help="Path to bot JSON. Shadow + emit use this candidate.")
    ap.add_argument("--live", action="store_true",
                    help="Drop shadow_mode on emitted JSON.")
    ap.add_argument("--audit", default=None,
                    help="Optional path to candidate audit JSON — enables backtest/summary emission.")
    ap.add_argument("--skip-pull", action="store_true")
    ap.add_argument("--skip-features", action="store_true")
    ap.add_argument("--skip-shadow", action="store_true")
    ap.add_argument("--skip-emit", action="store_true")
    args = ap.parse_args()

    py = sys.executable

    if not args.skip_pull:
        # Skip Stooq (JS challenge). EIA runs if EIA_API_KEY is set; the
        # eia puller no-ops silently when the key is missing.
        rc = _run([py, "scripts/pull_data.py", "--skip", "stooq"],
                  "pull_data (skip stooq)")
        if rc != 0:
            print("[warn] pull_data returned non-zero; continuing to features")

    if not args.skip_features:
        rc = _run([py, "scripts/build_features.py"], "build_features")
        if rc != 0:
            print("[fatal] features build failed")
            return 2

    if not args.skip_shadow:
        shadow_cmd = [py, "scripts/shadow_log.py"]
        if args.candidate:
            shadow_cmd += ["--candidate", args.candidate]
        rc = _run(shadow_cmd, "shadow_log")
        if rc != 0:
            print("[fatal] shadow_log failed")
            return 3

    if not args.skip_emit:
        emit_cmd = [py, "scripts/emit_reads.py"]
        if args.candidate:
            emit_cmd += ["--candidate", args.candidate]
        if args.audit:
            emit_cmd += ["--audit", args.audit]
        if args.live:
            emit_cmd += ["--live"]
        rc = _run(emit_cmd, "emit_reads")
        if rc != 0:
            print("[fatal] emit_reads failed")
            return 4

    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] pipeline done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
