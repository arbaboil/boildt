"""Feature-coverage guard — fails if any required feature column drops
below the coverage floor on the HOLDOUT slice.

Rationale (see memory/feedback_prefer_stable_ids_over_names.md):
On 2026-10-12 found the WTI COT puller had silently returned zero rows
since 2022-02 due to a CFTC contract rename. `cot_mm_net_wti` was NaN
for the entire HOLDOUT, so vote_cot = 0 on every live call for ~4
years. This test would have failed on the first HOLDOUT run after
the outage began.

Scope:
- Only features actually consumed by `score_matrix` / the shipped bot
  genome are gated. Optional features (rig count, hurricane) stay
  outside the gate until integrated.
- Floor is 80% non-null on the HOLDOUT slice (2024-01-01 → present).
  Lower bound chosen to accommodate expected gaps (holidays,
  publication lag) but trip loudly on a multi-week outage.

Skips cleanly if `data/processed/features.parquet` is missing (fresh
clone before any data pull) — the data pull is expected to run as a
separate CI step upstream.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
FEATURES = REPO / "data" / "processed" / "features.parquet"

# Floor + holdout start are policy decisions documented in PROTOCOL.md
# (HOLDOUT begins 2024-01-01) and feedback_prefer_stable_ids_over_names.md
# (80% chosen as the "silent-outage" trip level).
COVERAGE_FLOOR = 0.80
HOLDOUT_START = "2024-01-01"

# Required feature columns — every feature that `score_matrix` reads AND
# every raw price column the shipped bot's trade logic needs.
# Keep this list in sync with src/engine/regime_vote.py:score_matrix.
REQUIRED_COLS = [
    # Trade-level inputs
    "wti_close",
    "wti_atr20",
    "wti_atr20_pct",
    # Vote inputs
    "wti_ema50_slope",   # trend
    "wti_ret_20d",       # momentum
    "vix_z156w",         # vol
    "crack_spread_z",    # curve
    "cot_mm_net_wti_z",  # cot — silent-outage canary
    "eia_stocks_surprise",
    "dxy_ret_20d",       # macro
]


@pytest.fixture(scope="module")
def holdout_slice() -> pd.DataFrame:
    if not FEATURES.exists():
        pytest.skip(f"features parquet missing at {FEATURES} — run "
                    "scripts/build_features.py first")
    df = pd.read_parquet(FEATURES)
    df["date"] = pd.to_datetime(df["date"])
    ho = df[df["date"] >= HOLDOUT_START].copy()
    if ho.empty:
        pytest.skip("HOLDOUT slice empty — out of range or clock skew")
    return ho


@pytest.mark.parametrize("col", REQUIRED_COLS)
def test_feature_coverage_holdout(holdout_slice: pd.DataFrame, col: str) -> None:
    """Each required feature must be ≥80% non-null on the HOLDOUT slice."""
    assert col in holdout_slice.columns, (
        f"Required feature '{col}' missing from features.parquet. Check "
        f"the pull/build pipeline — a rename or schema change probably "
        f"dropped it silently."
    )
    coverage = holdout_slice[col].notna().mean()
    assert coverage >= COVERAGE_FLOOR, (
        f"Feature '{col}' coverage on HOLDOUT ({HOLDOUT_START}→): "
        f"{coverage:.1%} — below {COVERAGE_FLOOR:.0%} floor. This is the "
        f"silent-NaN canary. Investigate the puller for '{col}' — the "
        f"upstream source may have renamed/removed a series. See "
        f"memory/project_helios_silent_cot_outage_2026-10-12.md for the "
        f"canonical worked example."
    )
