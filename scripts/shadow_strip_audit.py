"""Shadow-strip quality audit.

Reconstructs each emitted weekly call's realized trade outcome from WTI daily
closes and compares against the model's walk-forward expectation.

Reads:
  - results/emitted/history/*weekly.json  (per-week call + trade levels)
  - results/shadow/*.json                 (daily shadow reads — direction mix)
  - data/raw/yahoo_wti_futures_yf.parquet (daily WTI closes)
  - results/ship_readiness.json           (model expectation: mean R on VAL/HO)

Writes:
  - results/shadow_audit.json

Reports: # closed trades, mean R realized (two conventions), # open, hit rate,
cumulative R, divergence from VAL + HOLDOUT expectation. A trade is CLOSED when
daily close touches stop/target *or* hold_days_max elapses.

Entry convention — two reported for honesty:
  (A) "ref" entry      : fill at suggested_entry_price (= Fri close, the price
                          members see on the site)
  (B) "next-close" entry: fill at next daily close after signal_date — matches
                          the walk-forward backtest convention
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_history() -> list[dict]:
    rows = []
    for p in sorted(Path("results/emitted/history").glob("*weekly.json")):
        with p.open(encoding="utf-8") as fh:
            d = json.load(fh)
        rows.append(d)
    return rows


def _load_shadow() -> pd.DataFrame:
    recs = []
    for p in sorted(Path("results/shadow").glob("*.json")):
        with p.open(encoding="utf-8") as fh:
            d = json.load(fh)
        recs.append({
            "as_of": d["as_of"],
            "read": d["read"],
            "confidence": d.get("confidence"),
            "ref": d.get("levels", {}).get("ref"),
            "is_candidate": d.get("is_candidate", False),
        })
    return pd.DataFrame(recs).sort_values("as_of").reset_index(drop=True)


def _simulate_trade(prices: pd.DataFrame, start_date: pd.Timestamp,
                    entry_px: float, stop_px: float, target_px: float,
                    direction: int, max_hold: int) -> dict:
    """Walk forward from start_date (exclusive) through max_hold bars. Return
    outcome, exit date, exit price, R, days_held."""
    sub = prices[prices["date"] > start_date].head(max_hold).reset_index(drop=True)
    outcome = "OPEN"
    exit_px = float("nan")
    exit_date = None
    hit_bar = None
    for i, row in sub.iterrows():
        px = row["close"]
        if pd.isna(px):
            continue
        hit_stop = (direction == 1 and px <= stop_px) or (direction == -1 and px >= stop_px)
        hit_target = (direction == 1 and px >= target_px) or (direction == -1 and px <= target_px)
        if hit_stop and hit_target:
            exit_px = stop_px  # honest: adverse first
            outcome = "STOP"
            exit_date = row["date"]
            hit_bar = i
            break
        if hit_stop:
            exit_px = stop_px
            outcome = "STOP"
            exit_date = row["date"]
            hit_bar = i
            break
        if hit_target:
            exit_px = target_px
            outcome = "TARGET"
            exit_date = row["date"]
            hit_bar = i
            break
    if outcome == "OPEN":
        if len(sub) >= max_hold:
            # Hold expired → TIME exit at last close
            last = sub.iloc[-1]
            exit_px = float(last["close"])
            outcome = "TIME"
            exit_date = last["date"]
            hit_bar = max_hold - 1
        else:
            # Still open — not yet enough bars
            if len(sub) > 0:
                exit_px = float(sub.iloc[-1]["close"])
                exit_date = sub.iloc[-1]["date"]
                hit_bar = len(sub) - 1

    r_denom = abs(entry_px - stop_px)
    r = direction * (exit_px - entry_px) / r_denom if r_denom > 0 and not pd.isna(exit_px) else None

    return {
        "outcome": outcome,
        "exit_date": str(exit_date.date()) if exit_date is not None else None,
        "exit_px": None if pd.isna(exit_px) else float(exit_px),
        "r": None if r is None else float(r),
        "days_held": (hit_bar + 1) if hit_bar is not None else 0,
    }


def main() -> int:
    prices = pd.read_parquet("data/raw/yahoo_wti_futures_yf.parquet")
    prices["date"] = pd.to_datetime(prices["date"]).dt.tz_localize(None)
    prices = prices.sort_values("date").reset_index(drop=True)

    history = _load_history()
    shadow = _load_shadow()

    # Model expectation from ship_readiness
    sr = json.loads(Path("results/ship_readiness.json").read_text(encoding="utf-8"))
    val_mean_r = sr["gate_2b_payoff_adjusted"]["VALIDATION"]["mean_r_net"]
    ho_mean_r = sr["gate_2b_payoff_adjusted"]["HOLDOUT"]["mean_r_net"]
    val_wr = sr["gate_2b_payoff_adjusted"]["VALIDATION"]["wr"]
    ho_wr = sr["gate_2b_payoff_adjusted"]["HOLDOUT"]["wr"]

    trades = []
    for d in history:
        wk = d["week_of"]
        direction = 1 if d["direction"] == "LONG" else -1
        levels = d.get("levels", {})
        entry_ref = levels.get("suggested_entry_price")
        stop_px = levels.get("suggested_stop_price_at_entry")
        target_px = levels.get("suggested_target_price_at_entry")
        max_hold = int(levels.get("hold_days_max", 11))
        signal_dt = pd.to_datetime(d.get("signal_date_utc")).tz_localize(None) if d.get("signal_date_utc") else pd.Timestamp(wk)

        # (A) Entry at ref — simulate from signal_date inclusive
        trade_ref = _simulate_trade(prices, signal_dt - pd.Timedelta(days=1),
                                    entry_ref, stop_px, target_px, direction, max_hold)
        # (B) Entry at next close
        nxt = prices[prices["date"] > signal_dt].head(1)
        if nxt.empty:
            trade_next = {"outcome": "NO_FILL", "r": None}
        else:
            entry_next = float(nxt.iloc[0]["close"])
            # Rescale stop/target to the next-close entry
            atr_mult_stop = levels.get("stop_atr_mult", 0.754)
            atr_mult_target = levels.get("target_atr_mult", 4.69)
            # Infer atr from original levels: atr = (entry_ref - stop_px) / stop_mult
            atr20 = abs(entry_ref - stop_px) / atr_mult_stop if atr_mult_stop else None
            if atr20 is None or atr20 <= 0:
                trade_next = {"outcome": "SKIP_ATR", "r": None}
            else:
                stop_next = entry_next - direction * atr_mult_stop * atr20
                target_next = entry_next + direction * atr_mult_target * atr20
                trade_next = _simulate_trade(prices, nxt.iloc[0]["date"],
                                             entry_next, stop_next, target_next,
                                             direction, max_hold)

        trades.append({
            "week_of": wk,
            "direction": d["direction"],
            "signal_date": str(signal_dt.date()),
            "entry_ref_px": entry_ref,
            "stop_ref_px": stop_px,
            "target_ref_px": target_px,
            "max_hold_days": max_hold,
            "ref_entry": trade_ref,
            "next_close_entry": trade_next,
        })

    closed_ref = [t for t in trades if t["ref_entry"]["outcome"] in ("STOP", "TARGET", "TIME")]
    closed_next = [t for t in trades if t["next_close_entry"]["outcome"] in ("STOP", "TARGET", "TIME")]

    def _stats(closed, key):
        if not closed:
            return {"n": 0}
        rs = [t[key]["r"] for t in closed if t[key]["r"] is not None]
        wins = [r for r in rs if r > 0]
        return {
            "n": len(rs),
            "mean_r": sum(rs) / len(rs) if rs else None,
            "cum_r": sum(rs),
            "wr": len(wins) / len(rs) if rs else None,
            "worst_r": min(rs) if rs else None,
            "best_r": max(rs) if rs else None,
        }

    stats_ref = _stats(closed_ref, "ref_entry")
    stats_next = _stats(closed_next, "next_close_entry")

    shadow_summary = {
        "n_shadow_days": int(len(shadow)),
        "direction_mix": shadow["read"].value_counts().to_dict(),
        "mean_confidence": float(shadow["confidence"].mean()) if len(shadow) else None,
        "first_asof": shadow["as_of"].iloc[0] if len(shadow) else None,
        "last_asof": shadow["as_of"].iloc[-1] if len(shadow) else None,
    }

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate": sr.get("candidate_stem"),
        "model_expectation": {
            "val_mean_r_net": val_mean_r,
            "val_wr": val_wr,
            "ho_mean_r_net": ho_mean_r,
            "ho_wr": ho_wr,
        },
        "shadow_strip": shadow_summary,
        "live_trades": trades,
        "realized_stats": {
            "ref_entry": stats_ref,
            "next_close_entry": stats_next,
        },
        "divergence": {
            "mean_r_vs_val": (stats_ref.get("mean_r") - val_mean_r) if stats_ref.get("mean_r") is not None else None,
            "mean_r_vs_ho": (stats_ref.get("mean_r") - ho_mean_r) if stats_ref.get("mean_r") is not None else None,
        },
        "notes": (
            "Mean R is point-estimate on a tiny sample; CI is wide. Treat <5 "
            "closed trades as directional-only evidence. True Gate 7 CI "
            "requires the full 28-day shadow window."
        ),
    }

    out = Path("results/shadow_audit.json")
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
