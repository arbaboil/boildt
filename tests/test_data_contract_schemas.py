"""Schema validation tests for emitted JSON per docs/DATA-CONTRACT.md.

Prevents accidental ship of malformed data to Vega's site loader.
These tests operate on the already-emitted artifacts under
`results/emitted/` — if those files are absent (e.g. on CI clone
before emit runs), the tests skip cleanly rather than fail.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EMITTED = REPO / "results" / "emitted"

VALID_DIRECTIONS = {"LONG", "SHORT", "FLAT", "SHADOW", "BUY", "SELL"}
VOTE_COMPONENTS = {"trend", "momentum", "vol", "curve", "cot", "eia", "macro"}


def _load_or_skip(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"emitted artifact missing (expected on fresh clone): {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================
# weekly/current.json
# ============================================================

def test_weekly_required_top_level_keys_present():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    for key in ("type", "schema_version", "instrument", "signal_date_utc",
                "published_utc", "direction", "shadow_mode",
                "current_price", "atr_20d", "signal_components",
                "confidence", "score"):
        assert key in d, f"weekly missing top-level key: {key}"


def test_weekly_type_is_call():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert d["type"] == "call"


def test_weekly_schema_version_int():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert isinstance(d["schema_version"], int)


def test_weekly_instrument_wti_or_brent():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert d["instrument"] in {"WTI", "brent"}


def test_weekly_direction_in_enum():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert d["direction"] in VALID_DIRECTIONS


def test_weekly_shadow_mode_is_bool():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert isinstance(d["shadow_mode"], bool)


def test_weekly_confidence_0_to_100():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    c = d["confidence"]
    assert isinstance(c, (int, float))
    assert 0 <= c <= 100, f"confidence out of range: {c}"


def test_weekly_score_signed_float():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert isinstance(d["score"], (int, float))
    assert -10.0 <= d["score"] <= 10.0


def test_weekly_current_price_positive():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert d["current_price"] > 0


def test_weekly_atr_20d_positive():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    assert d["atr_20d"] > 0


def test_weekly_signal_components_shape():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    sc = d["signal_components"]
    assert isinstance(sc, dict)
    for k in VOTE_COMPONENTS:
        assert k in sc, f"missing signal component: {k}"
        comp = sc[k]
        assert "vote" in comp and "weight" in comp
        assert comp["vote"] in {-1, 0, 1}
        assert comp["weight"] >= 0


def test_weekly_shadow_when_shadow_mode_true():
    d = _load_or_skip(EMITTED / "weekly" / "current.json")
    if d.get("shadow_mode") is True:
        assert d["direction"] == "SHADOW", (
            "direction must be SHADOW when shadow_mode is true "
            "(prevents site loader from surfacing live-labeled reads pre-Gate-7)"
        )


# ============================================================
# daily/current.json
# ============================================================

def test_daily_type_is_brief():
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    assert d["type"] == "brief"


def test_daily_has_as_of_not_week_of():
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    assert "as_of" in d, "daily brief must use as_of (not week_of)"


def test_daily_shadow_only_flag_present():
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    # daily is shadow-only until it clears daily-cadence gates
    assert "shadow_mode" in d or "shadow_only" in d


def test_daily_shares_direction_enum_with_weekly():
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    assert d["direction"] in VALID_DIRECTIONS


# ============================================================
# backtest/summary.json
# ============================================================

def test_backtest_summary_type():
    d = _load_or_skip(EMITTED / "backtest" / "summary.json")
    assert d["type"] == "backtest_summary"


def test_backtest_summary_has_candidate_and_protocol():
    d = _load_or_skip(EMITTED / "backtest" / "summary.json")
    assert "candidate" in d
    assert "protocol_version" in d


def test_backtest_summary_slices_present():
    d = _load_or_skip(EMITTED / "backtest" / "summary.json")
    assert "slices" in d
    slices = d["slices"]
    # At least one of the standard slices should be present
    assert any(k in slices for k in ("TRAIN", "VALIDATION", "HOLDOUT")), (
        "backtest summary missing all standard slices"
    )


# ============================================================
# Cross-file invariants
# ============================================================

def test_weekly_and_daily_instrument_match():
    """Weekly and daily should agree on which instrument they cover."""
    w = _load_or_skip(EMITTED / "weekly" / "current.json")
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    assert w["instrument"] == d["instrument"]


def test_weekly_and_daily_schema_versions_match():
    w = _load_or_skip(EMITTED / "weekly" / "current.json")
    d = _load_or_skip(EMITTED / "daily" / "current.json")
    assert w["schema_version"] == d["schema_version"]
