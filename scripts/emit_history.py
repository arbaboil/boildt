"""Weekly history archive + index emitter (per Vega ask 2, 2026-09-22).

Two responsibilities:

1. **Archive today's weekly call.** If `results/emitted/weekly/current.json`
   is a fresh week (`week_of` not already archived), copy the payload verbatim
   to `results/emitted/history/{week_of}-weekly.json`. Idempotent — re-runs
   on the same week no-op.

2. **Rebuild the index.** Scan `results/emitted/history/*-weekly.json`,
   assemble the ordered list per Vega's schema, resolve outcomes for
   weeks whose max-hold window has passed by walking forward through the
   feature matrix.

Output:
    results/emitted/history/index.json
    results/emitted/history/{week_of}-weekly.json (one per archived week)

Outcome resolution:
    Given a weekly call with direction, entry (current_price), stop, target,
    and max_hold_days, walk forward through daily wti_close values starting
    from the day after week_of.
    - If a close crosses target in the profitable direction → outcome = "target"
    - If a close crosses stop in the losing direction → outcome = "stop"
    - Neither in max_hold_days days → outcome = "max_hold", exit at last close
    - Direction "SHADOW" or "FLAT" → outcome carries direction only, no PnL
    Then compute net_return_pct = signed % move at exit.

Usage:
    python scripts/emit_history.py                     # normal daily invocation
    python scripts/emit_history.py --force-rebuild     # rebuild index even if unchanged
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.util.paths import DATA_PROCESSED

REPO = Path(__file__).resolve().parents[1]
EMITTED_WEEKLY = REPO / "results" / "emitted" / "weekly" / "current.json"
HISTORY_DIR = REPO / "results" / "emitted" / "history"
INDEX_PATH = HISTORY_DIR / "index.json"
SCHEMA_VERSION = 1

DIRECTIONAL = {"LONG", "SHORT", "BUY", "SELL"}


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _archive_current_weekly() -> str | None:
    """Copy weekly/current.json to history/{week_of}-weekly.json if fresh.
    Returns the week_of string of the archived file, or None if no-op."""
    payload = _load_json(EMITTED_WEEKLY)
    if payload is None:
        print("[emit_history] no current weekly.json; nothing to archive.")
        return None
    week_of = payload.get("week_of")
    if not week_of:
        print("[emit_history] current weekly.json missing week_of; skipping archive.")
        return None
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    dest = HISTORY_DIR / f"{week_of}-weekly.json"
    if dest.exists():
        # already archived; overwrite in case the same week's payload was
        # re-emitted with a corrected value (idempotent).
        dest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return week_of
    dest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"[emit_history] archived {dest.name}")
    return week_of


def _resolve_outcome(week: dict, prices: pd.DataFrame) -> dict:
    """Return {net_return_pct, exit_reason} for a resolved week, or None keys
    if the week is still open."""
    direction = week.get("direction")
    if direction not in DIRECTIONAL:
        return {"net_return_pct": None, "exit_reason": None}
    week_of = week.get("week_of")
    if not week_of:
        return {"net_return_pct": None, "exit_reason": None}
    entry = week.get("current_price")
    levels = week.get("levels") or {}
    max_hold = int(levels.get("hold_days_max") or week.get("max_hold_days") or 11)
    stop = (levels.get("suggested_stop_price_at_entry")
            if "suggested_stop_price_at_entry" in levels
            else levels.get("stop_long_at") or levels.get("stop_short_at"))
    target = (levels.get("suggested_target_price_at_entry")
              if "suggested_target_price_at_entry" in levels
              else levels.get("target_long_at") or levels.get("target_short_at"))
    if entry is None or stop is None or target is None:
        return {"net_return_pct": None, "exit_reason": None}

    entry_date = pd.Timestamp(week_of).tz_localize("UTC")
    is_long = direction in {"LONG", "BUY"}
    # Prices strictly after entry_date, up to max_hold_days trading days.
    future = prices[prices["date"] > entry_date].reset_index(drop=True)
    if future.empty:
        return {"net_return_pct": None, "exit_reason": None}
    window = future.head(max_hold)
    if len(window) < max_hold:
        # Window not yet complete — week still open.
        return {"net_return_pct": None, "exit_reason": None}
    exit_reason = None
    exit_price = None
    for _, row in window.iterrows():
        close = row["wti_close"]
        if pd.isna(close):
            continue
        if is_long:
            if close >= target:
                exit_reason = "target"
                exit_price = float(target)
                break
            if close <= stop:
                exit_reason = "stop"
                exit_price = float(stop)
                break
        else:
            if close <= target:
                exit_reason = "target"
                exit_price = float(target)
                break
            if close >= stop:
                exit_reason = "stop"
                exit_price = float(stop)
                break
    if exit_reason is None:
        exit_reason = "max_hold"
        last_close = window["wti_close"].dropna().iloc[-1] if not window["wti_close"].dropna().empty else None
        if last_close is None:
            return {"net_return_pct": None, "exit_reason": None}
        exit_price = float(last_close)

    signed_return = ((exit_price - float(entry)) / float(entry)) * (1 if is_long else -1)
    return {
        "net_return_pct": round(signed_return * 100.0, 2),
        "exit_reason": exit_reason,
    }


def _rebuild_index() -> dict:
    """Scan history/*-weekly.json, order oldest → newest, resolve outcomes."""
    features_df = None
    features_path = DATA_PROCESSED / "features.parquet"
    if features_path.exists():
        features_df = pd.read_parquet(features_path)
        features_df["date"] = pd.to_datetime(features_df["date"], utc=True)
        prices = features_df[["date", "wti_close"]].sort_values("date").reset_index(drop=True)
    else:
        prices = pd.DataFrame({"date": [], "wti_close": []})

    files = sorted(HISTORY_DIR.glob("*-weekly.json"))
    weeks: list[dict] = []
    for f in files:
        wk = _load_json(f)
        if wk is None:
            continue
        entry = {
            "week_of": wk.get("week_of"),
            "week_end": wk.get("week_end"),
            "direction": wk.get("direction"),
            "outcome": _resolve_outcome(wk, prices),
            "has_detail": True,
        }
        weeks.append(entry)
    weeks.sort(key=lambda w: w["week_of"] or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "weeks": weeks,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-rebuild", action="store_true",
                    help="Rebuild the index even if no new archive was written.")
    args = ap.parse_args()

    archived = _archive_current_weekly()
    if archived is None and not args.force_rebuild and INDEX_PATH.exists():
        print("[emit_history] no fresh archive and --force-rebuild not set; keeping index as-is.")
        return 0
    index = _rebuild_index()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")
    n = len(index["weeks"])
    resolved = sum(1 for w in index["weeks"] if w["outcome"]["exit_reason"])
    print(f"[emit_history] wrote {INDEX_PATH.name} — {n} weeks archived, {resolved} resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
