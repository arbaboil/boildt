"""Weekly history archive + index emitter (per Vega ask 2, 2026-09-22).

Two responsibilities:

1. **Archive today's weekly call.** If `results/emitted/weekly/current.json`
   is a fresh week (`week_of` not already archived), copy the payload verbatim
   to `results/emitted/history/{week_of}-weekly.json`. The first publish is
   the call of record; re-runs never overwrite it (frozen since 2026-11-10).

2. **Rebuild the index.** Scan `results/emitted/history/*-weekly.json`,
   assemble the ordered list per Vega's schema, resolve outcomes for
   weeks whose max-hold window has passed by walking forward through the
   feature matrix.

Output:
    results/emitted/history/index.json
    results/emitted/history/{week_of}-weekly.json (one per archived week)

Outcome resolution:
    Backtest-identical grading - see _resolve_outcome docstring. Entry is
    the first close after the signal bar; only later closes grade the call.
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
        # Published calls are FROZEN (2026-11-10). Never overwrite an
        # archived week; the first publish is the call of record.
        return week_of
    dest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"[emit_history] archived {dest.name}")
    return week_of


def _resolve_outcome(week: dict, prices: pd.DataFrame) -> dict:
    """Grade a published weekly call exactly like src/sim/backtest.py does.

    Method (locked 2026-11-10, replaces the pre-fix grader):
      * Signal bar = ``signal_date_utc`` (the close the call was computed on).
        Only bars strictly AFTER it are used, so nothing known at publish
        time can grade the call. (Pre-fix grading walked from ``week_of``
        while the call itself was re-priced daily later in the week, which
        let already-known closes trigger stops/targets.)
      * Entry = first valid close after the signal bar (backtest's
        next-close proxy for next-bar open; Monday close for a Friday call).
      * Stop / target = entry -/+ ``stop_atr_mult`` / ``target_atr_mult``
        x ``atr_20d`` from the payload; close-based checks; stop wins a tie.
      * Window = the ``hold_days_max`` business-day rows after entry.
      * Resolves as soon as stop/target is hit; otherwise ``max_hold`` once
        the window has fully elapsed, else still open (None, None).
      * Return is gross of costs (signed % move entry -> exit).
    """
    none = {"net_return_pct": None, "exit_reason": None}
    direction = week.get("direction")
    if direction not in DIRECTIONAL:
        return none
    levels = week.get("levels") or {}
    atr = week.get("atr_20d")
    price = week.get("current_price")
    if atr is None or price is None:
        return none
    k_stop = levels.get("stop_atr_mult")
    k_target = levels.get("target_atr_mult")
    if k_stop is None or k_target is None:
        st = levels.get("suggested_stop_price_at_entry")
        tg = levels.get("suggested_target_price_at_entry")
        if st is None or tg is None:
            return none
        k_stop = abs(float(price) - float(st)) / float(atr)
        k_target = abs(float(tg) - float(price)) / float(atr)
    max_hold = int(levels.get("hold_days_max") or week.get("max_hold_days") or 11)

    sig = week.get("signal_date_utc")
    if sig:
        sig_ts = pd.Timestamp(sig)
        sig_ts = sig_ts.tz_localize("UTC") if sig_ts.tzinfo is None else sig_ts.tz_convert("UTC")
    else:
        sig_ts = pd.Timestamp(week["week_of"]).tz_localize("UTC") - pd.Timedelta(days=3)

    after = prices[prices["date"] > sig_ts].reset_index(drop=True)
    valid = after["wti_close"].notna()
    if not valid.any():
        return none
    j0 = int(valid[valid].index[0])
    entry = float(after.loc[j0, "wti_close"])
    sgn = 1 if direction in {"LONG", "BUY"} else -1
    stop = entry - sgn * float(k_stop) * float(atr)
    target = entry + sgn * float(k_target) * float(atr)

    window = after.iloc[j0 + 1: j0 + 1 + max_hold]
    for _, row in window.iterrows():
        close = row["wti_close"]
        if pd.isna(close):
            continue
        hit_stop = sgn * (close - stop) <= 0
        hit_target = sgn * (close - target) >= 0
        if hit_stop or hit_target:
            exit_px = stop if hit_stop else target
            return {"net_return_pct": round(sgn * (exit_px - entry) / entry * 100.0, 2),
                    "exit_reason": "stop" if hit_stop else "target"}
    if len(window) < max_hold:
        return none
    closes = window["wti_close"].dropna()
    if closes.empty:
        return none
    exit_px = float(closes.iloc[-1])
    return {"net_return_pct": round(sgn * (exit_px - entry) / entry * 100.0, 2),
            "exit_reason": "max_hold"}


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
