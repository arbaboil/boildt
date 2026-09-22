"""Silent-live shadow logger.

Writes today's HELIOS reads to `results/shadow/YYYYMMDD.json`. Two modes:

  1. **Candidate shadow** (PROTOCOL gate 7). Pass `--candidate results/bots/
     bot_vX_seedN.json`. This records the candidate bot's genome-derived read
     with all trade levels, so we can later compare live behavior to the
     walk-forward envelope. Requires the candidate to have cleared gates
     1-6 first — the script does NOT check this; that's the owner's job.

  2. **Untuned engine trace** (default). Records engine v0.1 hand-picked
     defaults. This is a historical trace, NOT a ship shadow. It is safe
     to run before any candidate exists.

Discipline: PROTOCOL v0.1.0 says shadow window (≥ 4 weeks silent-live) starts
only *after* walk-forward gates 1-6 pass. Untuned traces do not count toward
that window. `is_candidate` field distinguishes.

Refuses to write if the effective as_of is older than the requested date —
otherwise a stale features parquet would silently produce a misleading
"today's read" that is actually last week's.

Usage:
    python scripts/shadow_log.py                     # untuned engine v0.1 for today
    python scripts/shadow_log.py --asof 2026-09-22   # specific date
    python scripts/shadow_log.py --candidate results/bots/bot_v3_seed1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import VoteConfig, score_matrix
from src.features.build import build_features
from src.util.paths import RESULTS_SHADOW


def _last_valid_index(features: pd.DataFrame) -> int:
    """Index of the last row with both a non-null wti_close AND non-null atr20.
    We skip holidays (NaN close) and pre-warmup rows (NaN ATR).
    """
    mask = features["wti_close"].notna() & features["wti_atr20"].notna()
    if not mask.any():
        return -1
    return int(mask[mask].index[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None,
                    help="ISO date. Defaults to today (UTC). "
                         "Refuses to write if data doesn't reach this date.")
    ap.add_argument("--candidate", default=None,
                    help="Path to a bot JSON. If provided, logs the candidate's "
                         "genome-derived read as the shadow entry.")
    ap.add_argument("--engine-tag", default="v0",
                    help="Tag written into the record (v0, v0.1, etc.). "
                         "Ignored when --candidate is provided (uses bot tag).")
    ap.add_argument("--allow-stale", action="store_true",
                    help="Write even if data is older than the requested asof. "
                         "Off by default so cron runs on stale data are visible.")
    args = ap.parse_args()

    if args.asof:
        target_date = pd.Timestamp(args.asof).tz_localize("UTC")
    else:
        target_date = pd.Timestamp(datetime.now(timezone.utc).date()).tz_localize("UTC")

    features = build_features()
    features["date"] = pd.to_datetime(features["date"])
    features = features[features["date"] <= target_date].reset_index(drop=True)
    if features.empty:
        raise SystemExit("No features rows at or before target date.")

    if args.candidate:
        bot = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        # evolve_bot.py writes 'best_genome'; freshseed_sweep.py writes 'genome'.
        genome = bot.get("best_genome") or bot.get("genome")
        if genome is None:
            raise SystemExit(f"Candidate {args.candidate} has neither "
                             f"'best_genome' nor 'genome' key.")
        vote_cfg, trade_cfg = genome_to_configs(genome)
        engine_tag = f"candidate:{Path(args.candidate).stem}"
        k_stop = trade_cfg.k_stop
        k_target = trade_cfg.k_target
        is_candidate = True
    else:
        vote_cfg = VoteConfig()
        trade_cfg = None
        engine_tag = args.engine_tag
        k_stop = 1.5
        k_target = 3.0
        is_candidate = False

    reads = score_matrix(features, vote_cfg)

    # Find the last row with a valid close AND ATR — skip holidays / pre-warmup.
    idx = _last_valid_index(features)
    if idx < 0:
        raise SystemExit("No valid trading day found.")
    latest_features = features.iloc[idx]
    latest_read = reads.iloc[idx]
    effective_asof = pd.Timestamp(latest_read["date"]).tz_convert("UTC").date()

    if effective_asof < target_date.date() and not args.allow_stale:
        raise SystemExit(
            f"Data is stale: requested asof {target_date.date()} but latest "
            f"valid trading day is {effective_asof}. "
            f"Run scripts/pull_data.py first, or pass --allow-stale to log anyway."
        )

    payload = {
        "as_of": str(effective_asof),
        "requested_asof": str(target_date.date()),
        "instrument": "WTI",
        "engine": engine_tag,
        "is_candidate": is_candidate,
        "read": latest_read["read"],
        "confidence": float(latest_read["confidence"]),
        "score": float(latest_read["score"]),
        "coverage": float(latest_read["coverage"]),
        "levels": {
            "ref": float(latest_features["wti_close"]),
            "atr20": float(latest_features["wti_atr20"]),
            "atr_k_stop": k_stop,
            "atr_k_target": k_target,
            "stop_long_at": float(latest_features["wti_close"] - k_stop * latest_features["wti_atr20"]),
            "target_long_at": float(latest_features["wti_close"] + k_target * latest_features["wti_atr20"]),
        },
        "votes": {
            "trend": int(latest_read["vote_trend"]),
            "momentum": int(latest_read["vote_momentum"]),
            "vol": int(latest_read["vote_vol"]),
            "curve": int(latest_read["vote_curve"]),
            "cot": int(latest_read["vote_cot"]),
            "eia": int(latest_read["vote_eia"]),
            "macro": int(latest_read["vote_macro"]),
        },
        "shadow_only": True,
        "helios_version": "0.1.0",
        "logged_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    RESULTS_SHADOW.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp(effective_asof).strftime("%Y%m%d")
    out = RESULTS_SHADOW / f"{stamp}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
