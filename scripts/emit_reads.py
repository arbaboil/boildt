"""Emit contract-compliant weekly-call and daily-brief JSON artifacts.

Produces files under `results/emitted/`:
  weekly/current.json
  daily/current.json
  backtest/summary.json  (if --candidate + --audit given)

These are the exact shapes documented in `docs/DATA-CONTRACT.md`. Vega's
site loader can pull these keys from R2 once they're uploaded.

Until PROTOCOL Gate 7 completes, all payloads carry `shadow_mode: true`
and `direction: "SHADOW"` (site renders "HELIOS calibrating").

Usage:
    python scripts/emit_reads.py --candidate results/bots/bot_v3_seed7_candidate.json \
                                 --audit results/bots/bot_v3_seed7_candidate_audit.json
    python scripts/emit_reads.py                        # untuned engine v0.1
    python scripts/emit_reads.py --live                 # drop shadow_mode
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import VoteConfig, score_matrix
from src.util.paths import DATA_PROCESSED

RESULTS_EMITTED = Path(__file__).resolve().parents[1] / "results" / "emitted"
KILLSWITCH_PATH = Path(__file__).resolve().parents[1] / "admin" / "killswitch.json"
SCHEMA_VERSION = 1
HELIOS_VERSION = "0.1.0"

# priceStep-style bounds (see docs/DEPLOY-PLAN.md — bump PROTOCOL if changed)
ATR_PCT_MIN = 0.005   # 0.5%
ATR_PCT_MAX = 0.10    # 10%
STOP_PRICE_MIN_MULT = 0.5
STOP_PRICE_MAX_MULT = 1.5


def _genome_hash(genome: dict) -> str:
    canonical = json.dumps(genome, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()[:32]


def _monday_and_sunday(d: pd.Timestamp) -> tuple[str, str]:
    monday = d - pd.Timedelta(days=d.weekday())
    sunday = monday + pd.Timedelta(days=6)
    return str(monday.date()), str(sunday.date())


def _feature_value(features: pd.DataFrame, idx: int, col: str):
    if col not in features.columns:
        return None
    v = features.iloc[idx].get(col)
    return None if pd.isna(v) else float(v)


def _last_valid_idx(features: pd.DataFrame) -> int:
    mask = features["wti_close"].notna() & features["wti_atr20"].notna()
    if not mask.any():
        raise SystemExit("No valid trading day in features.")
    return int(mask[mask].index[-1])


def _components(features: pd.DataFrame, idx: int, reads_row, vote_cfg) -> dict:
    """Map each vote group to {vote, weight, representative_value}."""
    return {
        "trend":    {"vote": int(reads_row["vote_trend"]),
                      "weight": vote_cfg.w_trend,
                      "value": _feature_value(features, idx, "wti_ema50_slope")},
        "momentum": {"vote": int(reads_row["vote_momentum"]),
                      "weight": vote_cfg.w_momentum,
                      "value": _feature_value(features, idx, "wti_ret_20d")},
        "vol":      {"vote": int(reads_row["vote_vol"]),
                      "weight": vote_cfg.w_vol,
                      "value": _feature_value(features, idx, "vix_z156w")},
        "curve":    {"vote": int(reads_row["vote_curve"]),
                      "weight": vote_cfg.w_curve,
                      "value": _feature_value(features, idx, "brent_wti_spread_z")},
        "cot":      {"vote": int(reads_row["vote_cot"]),
                      "weight": vote_cfg.w_cot,
                      "value": _feature_value(features, idx, "cot_mm_net_wti_z")},
        "eia":      {"vote": int(reads_row["vote_eia"]),
                      "weight": vote_cfg.w_eia,
                      "value": _feature_value(features, idx, "eia_stocks_surprise")},
        "macro":    {"vote": int(reads_row["vote_macro"]),
                      "weight": vote_cfg.w_macro,
                      "value": _feature_value(features, idx, "dxy_ret_20d")},
    }


def _direction(read: str) -> str:
    if read in ("BUY", "STRONG_BUY"):
        return "LONG"
    if read in ("SELL", "STRONG_SELL"):
        return "SHORT"
    return "FLAT"


def _message(direction: str, active_count: int, confidence: int, shadow: bool) -> str:
    if shadow:
        return "HELIOS shadow mode — this call resolves internally, not for member trading."
    if direction == "FLAT":
        return "No net directional edge this week; standing down."
    dir_word = "long" if direction == "LONG" else "short"
    return f"{active_count} components confirming {dir_word} bias; {confidence}% confidence."


def _primary_risk(direction: str, shadow: bool) -> dict:
    if shadow:
        return {"sentence": "Shadow mode: no live position risk.",
                "severity": "med", "trigger": None}
    if direction == "FLAT":
        return {"sentence": "Primary risk: missing a breakout while flat.",
                "severity": "med", "trigger": None}
    if direction == "LONG":
        return {"sentence": "Primary risk: DXY strength or curve flip reversing the bid.",
                "severity": "med", "trigger": None}
    return {"sentence": "Primary risk: demand-side shock (China stimulus, refinery restart) squeezing shorts.",
            "severity": "med", "trigger": None}


def _bounds_violated(price: float, atr: float, stop: float | None,
                     target: float | None) -> tuple[bool, str | None]:
    """priceStep-style bounds: reject absurd ATR or stop levels."""
    atr_pct = atr / price if price > 0 else float("inf")
    if not (ATR_PCT_MIN <= atr_pct <= ATR_PCT_MAX):
        return True, f"atr_pct={atr_pct:.4f} outside [{ATR_PCT_MIN},{ATR_PCT_MAX}]"
    if stop is not None:
        lo = STOP_PRICE_MIN_MULT * price
        hi = STOP_PRICE_MAX_MULT * price
        if not (lo <= stop <= hi):
            return True, f"stop={stop:.2f} outside [{lo:.2f},{hi:.2f}]"
    return False, None


def _levels(price: float, atr: float, direction: str, k_stop: float,
            k_target: float, max_hold: int) -> tuple[dict, bool, str | None]:
    stop = None
    target = None
    if direction == "LONG":
        stop = price - k_stop * atr
        target = price + k_target * atr
    elif direction == "SHORT":
        stop = price + k_stop * atr
        target = price - k_target * atr
    violated, why = _bounds_violated(price, atr, stop, target)
    levels = {
        "stop_atr_mult": k_stop,
        "target_atr_mult": k_target,
        "hold_days_max": max_hold,
        "suggested_entry_price": price,
        "suggested_stop_price_at_entry": None if violated else stop,
        "suggested_target_price_at_entry": None if violated else target,
    }
    return levels, violated, why


def _load_killswitch() -> tuple[bool, str | None]:
    if not KILLSWITCH_PATH.exists():
        return False, None
    try:
        ks = json.loads(KILLSWITCH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    if not ks.get("enabled"):
        return False, None
    # Optional expiry.
    exp = ks.get("expires_utc")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= exp_dt:
                return False, None
        except ValueError:
            pass
    return True, ks.get("reason")


def _build_call_payload(features: pd.DataFrame, reads: pd.DataFrame,
                        idx: int, vote_cfg, k_stop: float, k_target: float,
                        max_hold: int, candidate_stem: str | None,
                        genome_hash: str | None, shadow_mode: bool,
                        is_daily: bool) -> dict:
    row = reads.iloc[idx]
    latest = features.iloc[idx]
    direction = _direction(row["read"])
    published_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    signal_date_utc = pd.Timestamp(row["date"]).tz_convert("UTC").isoformat()
    confidence = int(round(float(row["confidence"]) * 100))
    price = float(latest["wti_close"])
    atr = float(latest["wti_atr20"])

    if is_daily:
        base = {
            "type": "brief",
            "as_of": str(pd.Timestamp(row["date"]).date()),
        }
    else:
        week_of, week_end = _monday_and_sunday(pd.Timestamp(row["date"]))
        base = {
            "type": "call",
            "week_of": week_of,
            "week_end": week_end,
        }

    components = _components(features, idx, row, vote_cfg)
    active_count = sum(1 for c in components.values() if c["vote"] != 0)
    null_components = [k for k, v in components.items() if v["value"] is None]

    kill_engaged, kill_reason = _load_killswitch()
    levels, bounds_violated, bounds_why = _levels(
        price, atr, direction, k_stop, k_target, max_hold)

    # Direction downgrade cascade: kill-switch > shadow_mode > bounds >
    # underlying direction.
    if kill_engaged:
        emitted_direction = "SHADOW"
        emit_message = f"HELIOS paused - {kill_reason or 'no reason given'}"
    elif shadow_mode:
        emitted_direction = "SHADOW"
        emit_message = _message(direction, active_count, confidence, True)
    elif bounds_violated:
        emitted_direction = "FLAT"
        emit_message = "Sanity-bounds violation - direction forced FLAT."
    else:
        emitted_direction = direction
        emit_message = _message(direction, active_count, confidence, False)

    payload = {
        **base,
        "schema_version": SCHEMA_VERSION,
        "instrument": "WTI",
        "signal_date_utc": signal_date_utc,
        "published_utc": published_utc,
        "direction": emitted_direction,
        "shadow_mode": shadow_mode,
        "current_price": price,
        "atr_20d": atr,
        "signal_components": components,
        "confidence": confidence,
        "score": float(row["score"]),
        "message": emit_message,
        "primary_risk": _primary_risk(direction, shadow_mode or kill_engaged),
        "provenance": {
            "candidate": candidate_stem,
            "protocol_version": HELIOS_VERSION,
            "genome_hash": genome_hash,
            "coverage": float(row["coverage"]),
            "null_components": null_components,
            "helios_version": HELIOS_VERSION,
            "kill_switch_engaged": kill_engaged,
            "kill_switch_reason": kill_reason,
            "bounds_violated": bounds_violated,
            "bounds_reason": bounds_why,
        },
        "live_pnl_pct": None,
        "live_updated_utc": None,
        "outcome": None,
        "levels": levels,
    }
    return payload


def _emit_backtest_summary(audit_path: Path) -> dict | None:
    if not audit_path.exists():
        return None
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    slices = {}
    for s in audit["slices"]:
        m = s["metrics"]
        slices[s["slice"]] = {
            "n": m["n_trades"],
            "wr": m["directional_wr"],
            "mean_r": m["mean_r_net"],
            "sharpe": m["sharpe_per_trade"],
            "sharpe_ci_low": s["bootstrap_sharpe"]["ci_low"],
            "max_dd_r": m["max_dd_r"],
            "perm_p": s["permutation"]["p_value"],
        }
    regime = audit.get("b6_regime_combined_train_val", {})
    return {
        "type": "backtest_summary",
        "schema_version": SCHEMA_VERSION,
        "candidate": Path(audit["candidate_source"]).stem,
        "protocol_version": HELIOS_VERSION,
        "slices": slices,
        "walkforward": {
            "k": audit["walkforward"]["k"],
            "positive_expectancy_folds": audit["walkforward"]["positive_expectancy_folds"],
            "pass_7of10_rule": audit["walkforward"]["pass_7of10_rule"],
        },
        "regime_by_regime": {
            r: {"n": (regime.get(r) or {}).get("n_trades"),
                "mean_r": (regime.get(r) or {}).get("mean_r_net")}
            for r in ("bull", "chop", "bear")
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None,
                    help="Path to bot JSON. If omitted, untuned engine v0.1 defaults are used.")
    ap.add_argument("--audit", default=None,
                    help="Path to a candidate audit JSON — enables backtest/summary.json emission.")
    ap.add_argument("--live", action="store_true",
                    help="Drop shadow_mode. Only pass after PROTOCOL Gate 7 completes.")
    ap.add_argument("--out-dir", default=None,
                    help="Override output directory (default results/emitted).")
    args = ap.parse_args()

    if args.candidate:
        cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        genome = cand.get("best_genome") or cand.get("genome")
        vote_cfg, trade_cfg = genome_to_configs(genome)
        candidate_stem = Path(args.candidate).stem
        genome_hash = _genome_hash(genome)
        k_stop = trade_cfg.k_stop
        k_target = trade_cfg.k_target
        max_hold = trade_cfg.max_hold_days
    else:
        vote_cfg = VoteConfig()
        candidate_stem = None
        genome_hash = None
        k_stop = 1.5
        k_target = 3.0
        max_hold = 20

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features.sort_values("date").reset_index(drop=True)
    reads = score_matrix(features, vote_cfg)
    idx = _last_valid_idx(features)

    out_dir = Path(args.out_dir) if args.out_dir else RESULTS_EMITTED
    (out_dir / "weekly").mkdir(parents=True, exist_ok=True)
    (out_dir / "daily").mkdir(parents=True, exist_ok=True)
    (out_dir / "backtest").mkdir(parents=True, exist_ok=True)

    shadow = not args.live
    weekly = _build_call_payload(features, reads, idx, vote_cfg,
                                 k_stop, k_target, max_hold,
                                 candidate_stem, genome_hash,
                                 shadow_mode=shadow, is_daily=False)
    daily = _build_call_payload(features, reads, idx, vote_cfg,
                                k_stop, k_target, max_hold,
                                candidate_stem, genome_hash,
                                shadow_mode=shadow, is_daily=True)

    (out_dir / "weekly" / "current.json").write_text(
        json.dumps(weekly, indent=2), encoding="utf-8")
    (out_dir / "daily" / "current.json").write_text(
        json.dumps(daily, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir/'weekly'/'current.json'}")
    print(f"Wrote {out_dir/'daily'/'current.json'}")

    if args.audit:
        summary = _emit_backtest_summary(Path(args.audit))
        if summary is not None:
            (out_dir / "backtest" / "summary.json").write_text(
                json.dumps(summary, indent=2, default=str), encoding="utf-8")
            print(f"Wrote {out_dir/'backtest'/'summary.json'}")

    print(f"\nDirection (as emitted): {weekly['direction']}   confidence={weekly['confidence']}%   "
          f"shadow_mode={weekly['shadow_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
