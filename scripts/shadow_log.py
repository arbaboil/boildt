"""Silent-live shadow logger.

Runs once (cron-friendly): reloads data, computes today's read, and appends
to results/shadow/YYYYMMDD.json. Does NOT publish. Only Owner sees these.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engine.regime_vote import VoteConfig, score_matrix
from src.features.build import build_features
from src.util.paths import RESULTS_SHADOW


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", default=None, help="ISO date; defaults to today")
    ap.add_argument("--engine", default="v0")
    args = ap.parse_args()

    features = build_features()
    features["date"] = pd.to_datetime(features["date"])

    if args.asof:
        asof = pd.Timestamp(args.asof).tz_localize("UTC")
        features = features[features["date"] <= asof]

    if features.empty:
        raise SystemExit("No features available")

    reads = score_matrix(features, VoteConfig())
    latest = reads.iloc[-1]
    last_close = features.iloc[-1]["wti_close"]
    atr = features.iloc[-1].get("wti_atr20", None)

    payload = {
        "as_of": str(pd.Timestamp(latest["date"]).date()),
        "instrument": "WTI",
        "engine": args.engine,
        "read": latest["read"],
        "confidence": float(latest["confidence"]),
        "score": float(latest["score"]),
        "coverage": float(latest["coverage"]),
        "levels": {
            "ref": float(last_close) if pd.notna(last_close) else None,
            "atr20": float(atr) if atr is not None and pd.notna(atr) else None,
            "atr_k_stop": 1.5,
            "atr_k_target": 3.0,
        },
        "votes": {
            "trend": int(latest["vote_trend"]),
            "momentum": int(latest["vote_momentum"]),
            "vol": int(latest["vote_vol"]),
            "curve": int(latest["vote_curve"]),
            "cot": int(latest["vote_cot"]),
            "eia": int(latest["vote_eia"]),
            "macro": int(latest["vote_macro"]),
        },
        "shadow_only": True,
        "helios_version": "0.1.0",
    }

    RESULTS_SHADOW.mkdir(parents=True, exist_ok=True)
    stamp = date.fromisoformat(payload["as_of"]).strftime("%Y%m%d")
    out = RESULTS_SHADOW / f"{stamp}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
