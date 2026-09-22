"""Unit tests for emit_reads sanity guards (bounds + kill-switch)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# emit_reads lives under scripts/, not src/ — add to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import emit_reads


def test_bounds_ok():
    v, why = emit_reads._bounds_violated(price=93.0, atr=2.1, stop=91.4, target=103.0)
    assert v is False and why is None


def test_bounds_atr_too_low():
    # atr 0.001% of price — a corrupted feed
    v, why = emit_reads._bounds_violated(price=100.0, atr=0.001, stop=99.9, target=100.1)
    assert v is True
    assert "atr_pct" in why


def test_bounds_atr_too_high():
    # atr 20% of price — regime blowout, don't trade
    v, why = emit_reads._bounds_violated(price=100.0, atr=20.0, stop=95.0, target=105.0)
    assert v is True
    assert "atr_pct" in why


def test_bounds_stop_absurd_below():
    v, why = emit_reads._bounds_violated(price=100.0, atr=2.0, stop=1.0, target=110.0)
    assert v is True
    assert "stop" in why


def test_bounds_stop_absurd_above():
    v, why = emit_reads._bounds_violated(price=100.0, atr=2.0, stop=200.0, target=90.0)
    assert v is True


def test_killswitch_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(emit_reads, "KILLSWITCH_PATH", tmp_path / "does_not_exist.json")
    engaged, reason = emit_reads._load_killswitch()
    assert engaged is False and reason is None


def test_killswitch_disabled(tmp_path, monkeypatch):
    p = tmp_path / "killswitch.json"
    p.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    monkeypatch.setattr(emit_reads, "KILLSWITCH_PATH", p)
    engaged, reason = emit_reads._load_killswitch()
    assert engaged is False


def test_killswitch_enabled(tmp_path, monkeypatch):
    p = tmp_path / "killswitch.json"
    p.write_text(json.dumps({"enabled": True, "reason": "test drill"}), encoding="utf-8")
    monkeypatch.setattr(emit_reads, "KILLSWITCH_PATH", p)
    engaged, reason = emit_reads._load_killswitch()
    assert engaged is True and reason == "test drill"


def test_killswitch_expired(tmp_path, monkeypatch):
    p = tmp_path / "killswitch.json"
    p.write_text(json.dumps({
        "enabled": True,
        "reason": "past",
        "expires_utc": "2020-01-01T00:00:00Z",
    }), encoding="utf-8")
    monkeypatch.setattr(emit_reads, "KILLSWITCH_PATH", p)
    engaged, reason = emit_reads._load_killswitch()
    assert engaged is False


def test_killswitch_malformed(tmp_path, monkeypatch):
    p = tmp_path / "killswitch.json"
    p.write_text("{ malformed", encoding="utf-8")
    monkeypatch.setattr(emit_reads, "KILLSWITCH_PATH", p)
    engaged, reason = emit_reads._load_killswitch()
    # Malformed defaults to "off" to avoid failing open.
    assert engaged is False
