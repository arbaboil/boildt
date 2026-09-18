"""Project paths."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_CACHE = ROOT / "data" / "cache"
RESULTS = ROOT / "results"
RESULTS_BACKTESTS = RESULTS / "backtests"
RESULTS_WALKFORWARD = RESULTS / "walkforward"
RESULTS_MC = RESULTS / "monte_carlo"
RESULTS_SHADOW = RESULTS / "shadow"
RESULTS_BOTS = RESULTS / "bots"
HANDOFF = ROOT / "handoff"


def ensure_dirs() -> None:
    for p in [
        DATA_RAW,
        DATA_PROCESSED,
        DATA_CACHE,
        RESULTS_BACKTESTS,
        RESULTS_WALKFORWARD,
        RESULTS_MC,
        RESULTS_SHADOW,
        RESULTS_BOTS,
        HANDOFF,
    ]:
        p.mkdir(parents=True, exist_ok=True)
