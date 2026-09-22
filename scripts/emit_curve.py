"""Emit HOLDOUT equity curve + buy-hold benchmark per Vega's ask.

Runs bot v3 seed 7 (or configured candidate) on the HOLDOUT slice
(2024-01-01 → present), extracts per-trade cumulative R, computes the
buy-hold WTI benchmark on the same window scaled into R-units so the
site overlay is directly comparable, and writes:

    results/emitted/backtest/curve.json

Schema (per Vega 2026-09-22):
{
  "schema_version": 1,
  "sample": {
    "start_utc": "2024-01-02",
    "end_utc":   "2026-09-22",
    "price_source": "FRED WTI (DCOILWTICO) + Yahoo CL=F futures overlay",
    "notes": "HOLDOUT curve — training/validation slices excluded"
  },
  "equity_curve": [ { "date": ..., "cum_r": ..., "direction": ..., "r": ... }, ... ],
  "buy_hold_curve": [ { "date": ..., "cum_r": ... }, ... ],
  "buy_hold_summary": {
    "final_cum_r": ...,
    "max_drawdown_r": ...,
    "strategy_pct_of_hodl_pnl": ...,
    "strategy_dd_pct_of_hodl_dd": ...
  }
}

Buy-hold R scaling: converts cumulative return in $ per barrel into R
units by dividing the running $ move by the median 20-day ATR observed
over the HOLDOUT window. This is dimensionless and comparable to
strategy trade R values.

Usage:
    python scripts/emit_curve.py                   # engine v0.1 defaults
    python scripts/emit_curve.py --candidate results/bots/bot_v3_seed7_candidate.json
    python scripts/emit_curve.py --out custom.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import VoteConfig, score_matrix
from src.sim.backtest import TradeConfig, simulate
from src.util.paths import DATA_PROCESSED

HOLDOUT_START = "2024-01-01"
SCHEMA_VERSION = 1


def _cummax(x: np.ndarray) -> np.ndarray:
    return np.maximum.accumulate(x)


def _max_drawdown(cum: np.ndarray) -> float:
    if len(cum) == 0:
        return 0.0
    return float(np.min(cum - _cummax(cum)))


def build_curve(features: pd.DataFrame, vote_cfg: VoteConfig,
                 trade_cfg: TradeConfig, holdout_start: str) -> dict:
    """Simulate seed on HOLDOUT, produce equity + buy-hold benchmark."""
    lo = pd.to_datetime(holdout_start, utc=True)
    hi = features["date"].max()
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    slc = joined[joined["date"] >= lo].reset_index(drop=True)
    if slc.empty:
        return _empty_payload(holdout_start, hi)

    trades = simulate(slc, trade_cfg)
    # Per-trade equity curve, exit-date ordered.
    if trades.empty:
        equity = []
    else:
        trades = trades.sort_values("exit_date").reset_index(drop=True)
        cum = trades["r_net"].cumsum()
        equity = [
            {
                "date": str(pd.to_datetime(row["exit_date"]).date()),
                "cum_r": round(float(cum.iloc[i]), 4),
                "direction": "LONG" if row["direction"] == 1 else "SHORT",
                "r": round(float(row["r_net"]), 4),
            }
            for i, (_, row) in enumerate(trades.iterrows())
        ]

    # Buy-hold benchmark on the same date window, weekly Monday sampling
    # so the overlay isn't a daily noise wall.
    holdout_prices = slc[["date", "wti_close"]].dropna().reset_index(drop=True)
    if len(holdout_prices) < 2:
        buy_hold, bh_summary = [], _empty_buy_hold_summary()
    else:
        # Median ATR pct over holdout → 1R normalization anchor.
        atr_pct = slc["wti_atr20_pct"].dropna()
        r_anchor_pct = float(atr_pct.median()) if not atr_pct.empty else 0.02
        # Weekly-anchored buy-hold: pick Monday-closest samples.
        holdout_prices["date"] = pd.to_datetime(holdout_prices["date"], utc=True)
        weekly = holdout_prices.set_index("date").resample("W-MON").last().dropna().reset_index()
        if weekly.empty:
            buy_hold, bh_summary = [], _empty_buy_hold_summary()
        else:
            initial_price = float(weekly["wti_close"].iloc[0])
            # cum return in R = (price / initial - 1) / r_anchor_pct
            cum_r_series = (weekly["wti_close"].astype(float) / initial_price - 1.0) / max(r_anchor_pct, 1e-6)
            buy_hold = [
                {
                    "date": str(dt.date()),
                    "cum_r": round(float(cr), 4),
                }
                for dt, cr in zip(weekly["date"], cum_r_series)
            ]
            bh_final = float(cum_r_series.iloc[-1])
            bh_max_dd = _max_drawdown(cum_r_series.to_numpy())
            strat_final = float(cum.iloc[-1]) if not trades.empty else 0.0
            strat_dd = _max_drawdown(cum.to_numpy()) if not trades.empty else 0.0
            def _ratio(num, den):
                if den == 0 or den is None:
                    return None
                return round(float(num) / float(den), 4)
            bh_summary = {
                "final_cum_r": round(bh_final, 4),
                "max_drawdown_r": round(bh_max_dd, 4),
                "strategy_pct_of_hodl_pnl": _ratio(strat_final, bh_final),
                "strategy_dd_pct_of_hodl_dd": _ratio(strat_dd, bh_max_dd),
            }

    return {
        "schema_version": SCHEMA_VERSION,
        "sample": {
            "start_utc": str(pd.to_datetime(holdout_start).date()),
            "end_utc":   str(pd.to_datetime(hi).date()),
            "price_source": "FRED WTI (DCOILWTICO) + Yahoo CL=F futures overlay",
            "notes": "HOLDOUT curve — training/validation slices excluded",
        },
        "equity_curve": equity,
        "buy_hold_curve": buy_hold,
        "buy_hold_summary": bh_summary,
    }


def _empty_payload(start: str, hi) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "sample": {"start_utc": str(pd.to_datetime(start).date()),
                    "end_utc": str(pd.to_datetime(hi).date()),
                    "price_source": "FRED WTI + Yahoo CL=F",
                    "notes": "HOLDOUT empty"},
        "equity_curve": [],
        "buy_hold_curve": [],
        "buy_hold_summary": _empty_buy_hold_summary(),
    }


def _empty_buy_hold_summary() -> dict:
    return {
        "final_cum_r": 0.0,
        "max_drawdown_r": 0.0,
        "strategy_pct_of_hodl_pnl": None,
        "strategy_dd_pct_of_hodl_dd": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None,
                    help="Path to bot JSON. If omitted, engine v0.1 defaults.")
    ap.add_argument("--out", default="results/emitted/backtest/curve.json")
    ap.add_argument("--holdout-start", default=HOLDOUT_START)
    args = ap.parse_args()

    if args.candidate:
        cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        genome = cand.get("genome") or cand.get("best_genome")
        vote_cfg, trade_cfg = genome_to_configs(genome)
    else:
        vote_cfg = VoteConfig()
        trade_cfg = TradeConfig()

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features.sort_values("date").reset_index(drop=True)

    payload = build_curve(features, vote_cfg, trade_cfg, args.holdout_start)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    n_eq = len(payload["equity_curve"])
    n_bh = len(payload["buy_hold_curve"])
    print(f"[emit_curve] wrote {out_path}")
    print(f"  equity trades: {n_eq}")
    print(f"  buy-hold weekly points: {n_bh}")
    if payload["equity_curve"]:
        final_cum = payload["equity_curve"][-1]["cum_r"]
        print(f"  strategy final cum_r: {final_cum:+.2f}")
    if payload["buy_hold_summary"]["final_cum_r"]:
        print(f"  buy-hold final cum_r: {payload['buy_hold_summary']['final_cum_r']:+.2f}")
        print(f"  strategy % of buy-hold PnL: {payload['buy_hold_summary']['strategy_pct_of_hodl_pnl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
