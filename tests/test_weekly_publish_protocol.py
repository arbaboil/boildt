"""Weekly publish protocol (2026-11-10): completed-bar rule, Friday signal
rule, frozen archive, backtest-identical grading."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.util.session import (drop_incomplete_bars, last_complete_bar_date,  # noqa: E402
                              last_weekday_on_or_before, week_of_for_signal_friday,
                              weekly_signal_friday)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def test_in_progress_bar_excluded():
    # Tue 03:06 UTC: Tuesday's CME session is open, bar not final.
    assert last_complete_bar_date(T("2026-11-10 03:06")) == T("2026-11-09")
    assert last_complete_bar_date(T("2026-11-10 21:59")) == T("2026-11-09")
    assert last_complete_bar_date(T("2026-11-10 22:00")) == T("2026-11-10")
    df = pd.DataFrame({"date": [T("2026-11-09"), T("2026-11-10")], "x": [1, 2]})
    assert list(drop_incomplete_bars(df, T("2026-11-10 03:06"))["x"]) == [1]


def test_slipped_friday_run_targets_friday_not_saturday():
    # Fri 21:00 run slipping to Sat 00:34 used to request Saturday -> stale fail.
    d = last_weekday_on_or_before(last_complete_bar_date(T("2026-11-07 00:34")))
    assert d == T("2026-11-06")


def test_weekly_signal_friday_and_week_of():
    # Any time from Fri 22:00 through next Fri 21:59 maps to the same Friday.
    for now in ["2026-11-06 22:00", "2026-11-07 12:00", "2026-11-08 19:00",
                "2026-11-09 00:10", "2026-11-13 21:59"]:
        assert weekly_signal_friday(T(now)) == T("2026-11-06"), now
    assert weekly_signal_friday(T("2026-11-13 22:00")) == T("2026-11-13")
    assert week_of_for_signal_friday(T("2026-11-13")) == ("2026-11-16", "2026-11-22")


def _prices(closes, start="2026-11-06"):
    dates = pd.bdate_range(start, periods=len(closes), tz="UTC")
    return pd.DataFrame({"date": dates, "wti_close": closes})


def _call(direction="LONG", price=100.0, atr=2.0, sig="2026-11-06"):
    return {"week_of": "2026-11-09", "direction": direction, "current_price": price,
            "atr_20d": atr, "signal_date_utc": T(sig).isoformat(),
            "levels": {"stop_atr_mult": 1.0, "target_atr_mult": 2.0, "hold_days_max": 3}}


def test_grader_ignores_signal_bar_and_enters_next_close():
    eh = _load("emit_history")
    # signal Fri close 100 (ignored); entry Mon 100; stop 98 / target 104.
    out = eh._resolve_outcome(_call(), _prices([100, 100, 101, 104.5, 90]))
    assert out == {"net_return_pct": 4.0, "exit_reason": "target"}


def test_grader_resolves_early_stop_before_window_complete():
    eh = _load("emit_history")
    out = eh._resolve_outcome(_call(), _prices([100, 100, 97]))
    assert out == {"net_return_pct": -2.0, "exit_reason": "stop"}


def test_grader_open_until_window_elapses_then_max_hold():
    eh = _load("emit_history")
    assert eh._resolve_outcome(_call(), _prices([100, 100, 101]))["exit_reason"] is None
    out = eh._resolve_outcome(_call(), _prices([100, 100, 101, 102, 101]))
    assert out == {"net_return_pct": 1.0, "exit_reason": "max_hold"}


def test_grader_short_and_flat():
    eh = _load("emit_history")
    out = eh._resolve_outcome(_call("SHORT"), _prices([100, 100, 103]))
    assert out == {"net_return_pct": -2.0, "exit_reason": "stop"}
    assert eh._resolve_outcome(_call("FLAT"), _prices([100, 100, 103]))["exit_reason"] is None


def test_archive_never_overwrites(tmp_path, monkeypatch):
    eh = _load("emit_history")
    hist = tmp_path / "history"; hist.mkdir()
    cur = tmp_path / "current.json"
    monkeypatch.setattr(eh, "HISTORY_DIR", hist)
    monkeypatch.setattr(eh, "EMITTED_WEEKLY", cur)
    cur.write_text(json.dumps({"week_of": "2026-11-16", "direction": "LONG"}))
    assert eh._archive_current_weekly() == "2026-11-16"
    cur.write_text(json.dumps({"week_of": "2026-11-16", "direction": "SHORT"}))
    eh._archive_current_weekly()
    assert json.loads((hist / "2026-11-16-weekly.json").read_text())["direction"] == "LONG"


def test_nymex_holidays():
    from src.util.session import is_nymex_holiday, last_trading_day_on_or_before
    assert is_nymex_holiday(T("2026-11-26"))          # Thanksgiving
    assert is_nymex_holiday(T("2026-12-25"))          # Christmas (Fri)
    assert is_nymex_holiday(T("2026-04-03"))          # Good Friday 2026
    assert not is_nymex_holiday(T("2026-11-11"))      # Veterans Day trades
    assert not is_nymex_holiday(T("2026-10-12"))      # Columbus Day trades
    # Thanksgiving-night run expects Wednesday's bar, not a stale fail.
    assert last_trading_day_on_or_before(last_complete_bar_date(T("2026-11-26 22:30"))) == T("2026-11-25")
