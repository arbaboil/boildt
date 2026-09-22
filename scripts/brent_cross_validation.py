"""Brent cross-crude validation of bot v3 seed 7.

Independent-instrument test: does seed 7's VoteConfig + TradeConfig
produce edge on Brent as well as WTI? If yes, the strategy captures
a real crude-complex signal, not a WTI-specific artifact. If no, the
strategy is WTI-idiosyncratic and its Sharpe CI on VAL/HOLDOUT may be
partially in-distribution noise.

Approach:
  1. Load features.parquet.
  2. Substitute wti_close -> brent_close everywhere the votes read
     price-derived signals (trend, momentum, ATR, RSI, MACD, Donchian).
  3. Keep macro / positioning / EIA features untouched — those are
     crude-complex-wide, not WTI-specific.
  4. Score reads with seed 7's VoteConfig.
  5. Simulate trades on Brent price with seed 7's TradeConfig.
  6. Report metrics per slice.

If Brent Sharpe CI > 0 on all slices, we have external validation.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.genome import genome_to_configs
from src.engine.regime_vote import score_matrix
from src.features import indicators as I
from src.sim.backtest import simulate
from src.sim.metrics import block_bootstrap_sharpe, compute
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS

TRAIN = ("2006-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def brent_substituted_features(features: pd.DataFrame) -> pd.DataFrame:
    """Recompute price-derived features from Brent close, keep everything
    else. Returns a dataframe with the same column names the VoteConfig
    expects (wti_ema50_slope, wti_ret_20d, wti_atr20, etc.) but computed
    from Brent price.
    """
    out = features.copy()
    if "brent_close" not in out.columns:
        raise SystemExit("brent_close missing from features.parquet")

    brent_raw = out["brent_close"].astype(float)
    brent = brent_raw.ffill()

    # Substitute the WTI price and all price-derived features
    out["wti_close_orig"] = out["wti_close"]  # preserve for reference
    out["wti_close"] = brent_raw              # backtest will use this as trade price
    out["wti_ret_1d"] = I.log_returns(brent)
    out["wti_ret_5d"] = np.log(brent / brent.shift(5))
    out["wti_ret_20d"] = np.log(brent / brent.shift(20))
    out["wti_ret_60d"] = np.log(brent / brent.shift(60))
    out["wti_ema20_slope"] = I.slope(I.ema(brent, 20), 20)
    out["wti_ema50_slope"] = I.slope(I.ema(brent, 50), 20)
    out["wti_ema200_slope"] = I.slope(I.ema(brent, 200), 60)
    out["wti_rsi14"] = I.rsi(brent, 14)
    out["wti_macd_hist"] = I.macd_hist(brent)
    out["wti_donchian55"] = I.donchian_position(brent, 55)
    out["wti_rv20"] = I.realized_vol(brent, 20)
    out["wti_rv60"] = I.realized_vol(brent, 60)
    out["wti_atr20"] = I.atr_from_close(brent, 20)
    out["wti_atr20_pct"] = out["wti_atr20"] / brent
    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def slice_report(joined: pd.DataFrame, tcfg, name: str, start: str, end: str) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(slc, tcfg)
    m = compute(trades)
    boot = block_bootstrap_sharpe(trades, n_boot=5000, seed=1234)
    return {"slice": name, "start": start, "end": end,
            "metrics": asdict(m), "bootstrap_sharpe": boot}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="results/bots/bot_v3_seed7_candidate.json")
    ap.add_argument("--out", default="results/bots/bot_v3_seed7_candidate_brent_validation.json")
    args = ap.parse_args()

    cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    genome = cand.get("genome") or cand.get("best_genome")
    vote_cfg, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features.sort_values("date").reset_index(drop=True)

    brent_features = brent_substituted_features(features)

    # Score reads on the Brent-substituted feature matrix
    reads = score_matrix(brent_features, vote_cfg)
    joined = brent_features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )

    holdout_end = str(brent_features["date"].max().date())
    slices = [
        slice_report(joined, trade_cfg, "TRAIN", *TRAIN),
        slice_report(joined, trade_cfg, "VALIDATION", *VAL),
        slice_report(joined, trade_cfg, "HOLDOUT", HOLDOUT_START, holdout_end),
    ]

    # Compare to the original WTI reference (from candidate audit)
    wti_ref_path = Path("results/bots/bot_v3_seed7_candidate_audit.json")
    wti_ref = None
    if wti_ref_path.exists():
        aud = json.loads(wti_ref_path.read_text(encoding="utf-8"))
        wti_ref = {s["slice"]: {
            "wr": s["metrics"]["directional_wr"],
            "mean_r_net": s["metrics"]["mean_r_net"],
            "sharpe": s["metrics"]["sharpe_per_trade"],
            "ci_low": s["bootstrap_sharpe"]["ci_low"],
        } for s in aud["slices"]}

    verdict = {
        "n_slices_pass_g1": sum(1 for s in slices if s["bootstrap_sharpe"]["ci_low"] > 0),
        "n_slices_pass_g2_wr50": sum(1 for s in slices if s["metrics"]["directional_wr"] >= 0.50),
        "n_slices_positive_mean_r": sum(1 for s in slices if s["metrics"]["mean_r_net"] > 0),
        "generalizes_to_brent": None,
    }
    if verdict["n_slices_pass_g1"] >= 2 and verdict["n_slices_positive_mean_r"] == 3:
        verdict["generalizes_to_brent"] = "yes — cross-crude validation succeeds"
    elif verdict["n_slices_positive_mean_r"] >= 2:
        verdict["generalizes_to_brent"] = "partial — mean R positive on 2/3 slices"
    else:
        verdict["generalizes_to_brent"] = "no — WTI-specific edge, does not generalize to Brent"

    out = {
        "candidate": args.candidate,
        "instrument": "Brent",
        "trade_cfg": {"k_stop": trade_cfg.k_stop, "k_target": trade_cfg.k_target,
                      "max_hold_days": trade_cfg.max_hold_days,
                      "rr": trade_cfg.k_target / trade_cfg.k_stop},
        "slices": slices,
        "wti_reference": wti_ref,
        "verdict": verdict,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    print(f"=== Brent cross-crude validation — seed 7 ===")
    for s in slices:
        m = s["metrics"]; b = s["bootstrap_sharpe"]
        print(f"{s['slice']:12s}  n={m['n_trades']:3d}  WR={m['directional_wr']:.0%}  "
              f"mean_R={m['mean_r_net']:+.3f}  Sharpe={m['sharpe_per_trade']:+.2f}  "
              f"CI=[{b['ci_low']:+.2f}, {b['ci_high']:+.2f}]  max_dd={m['max_dd_r']:.1f}R")
    if wti_ref:
        print("\nWTI reference (from candidate audit):")
        for slice_name, r in wti_ref.items():
            print(f"  {slice_name:12s}  WR={r['wr']:.0%}  mean_R={r['mean_r_net']:+.3f}  "
                  f"Sharpe={r['sharpe']:+.2f}  CI_low={r['ci_low']:+.2f}")
    print(f"\nVerdict: {verdict['generalizes_to_brent']}")
    print(f"  slices passing G1 (Sharpe CI > 0): {verdict['n_slices_pass_g1']}/3")
    print(f"  slices passing WR >= 50%: {verdict['n_slices_pass_g2_wr50']}/3")
    print(f"  slices with positive mean R: {verdict['n_slices_positive_mean_r']}/3")
    print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
