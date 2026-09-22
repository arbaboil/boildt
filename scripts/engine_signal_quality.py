"""Signal-quality metrics for engine-only ship path (fallback if
PROTOCOL v0.2.0 is rejected).

Evaluates the engine's REGIME_VOTE output as a signal (independent of
any trade config) against forward WTI returns. These metrics do not
depend on the WR gate or Sharpe CI on simulated trades — they measure
whether the read itself carries information about direction.

Metrics:
  - Information Coefficient (IC): Spearman correlation of confidence
    (signed by direction: +conf for BUY, -conf for SELL, 0 for FLAT)
    with N-day forward return.
  - Read coverage: fraction of days with a non-FLAT read.
  - Read stability: fraction of consecutive days where the read did
    not change (higher = smoother signal, lower churn).
  - Directional accuracy (excl FLAT): fraction of directional reads
    where sign(read) == sign(forward return). This is a WR-analog for
    the signal itself, but at the READ level not the trade level.

Usage:
    python scripts/engine_signal_quality.py                       # engine v0.1 defaults
    python scripts/engine_signal_quality.py --candidate results/bots/bot_v3_seed7_candidate.json
    python scripts/engine_signal_quality.py --horizon 5 10 20 60  # multi-horizon IC

Reports per-slice (TRAIN / VAL / HOLDOUT).
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
from src.util.paths import DATA_PROCESSED

TRAIN = ("2001-01-01", "2018-12-31")
VAL = ("2019-01-01", "2023-12-31")
HOLDOUT_START = "2024-01-01"


def read_to_signed_confidence(reads_df: pd.DataFrame) -> pd.Series:
    """Convert (read, confidence) -> signed confidence in [-1, +1]."""
    sign = reads_df["read"].map({
        "STRONG_BUY": 1, "BUY": 1, "FLAT": 0,
        "SELL": -1, "STRONG_SELL": -1,
    }).astype(float)
    return sign * reads_df["confidence"]


def compute_ic(signed_conf: pd.Series, fwd_ret: pd.Series) -> dict:
    """Spearman rank correlation. Drops NaN pairs."""
    df = pd.concat([signed_conf.rename("sc"), fwd_ret.rename("fr")], axis=1)
    df = df.dropna()
    if len(df) < 30:
        return {"ic": None, "n": len(df)}
    ic = df["sc"].corr(df["fr"], method="spearman")
    return {"ic": float(ic), "n": int(len(df))}


def compute_coverage(reads_df: pd.DataFrame) -> float:
    non_flat = (reads_df["read"] != "FLAT").sum()
    return float(non_flat / len(reads_df)) if len(reads_df) > 0 else 0.0


def compute_read_stability(reads_df: pd.DataFrame) -> float:
    if len(reads_df) < 2:
        return 1.0
    same = (reads_df["read"].shift(1) == reads_df["read"]).sum()
    return float(same / (len(reads_df) - 1))


def compute_directional_accuracy(reads_df: pd.DataFrame,
                                    fwd_ret: pd.Series) -> dict:
    """Ignore FLAT rows. For directional reads, WR = sign match with
    forward return."""
    df = pd.concat([
        reads_df[["read"]].reset_index(drop=True),
        fwd_ret.reset_index(drop=True).rename("fr"),
    ], axis=1)
    df = df.dropna(subset=["fr"])
    directional = df[df["read"] != "FLAT"].copy()
    if len(directional) == 0:
        return {"n_directional": 0, "directional_wr": None, "flat_rate": 1.0}
    directional["is_buy"] = directional["read"].isin(["BUY", "STRONG_BUY"])
    correct = (
        (directional["is_buy"] & (directional["fr"] > 0))
        | (~directional["is_buy"] & (directional["fr"] < 0))
    ).sum()
    return {
        "n_directional": int(len(directional)),
        "directional_wr": float(correct / len(directional)),
        "flat_rate": float((df["read"] == "FLAT").sum() / len(df)),
    }


def slice_report(joined: pd.DataFrame, name: str, start: str, end: str,
                 horizons: list[int]) -> dict:
    lo = pd.to_datetime(start, utc=True)
    hi = pd.to_datetime(end, utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    signed_conf = read_to_signed_confidence(slc)

    ic_by_h = {}
    for h in horizons:
        ret_col = f"wti_ret_{h}d_fwd"
        if ret_col not in slc.columns:
            slc[ret_col] = np.log(slc["wti_close"].shift(-h) / slc["wti_close"])
        ic_by_h[f"ic_{h}d"] = compute_ic(signed_conf, slc[ret_col])

    coverage = compute_coverage(slc)
    stability = compute_read_stability(slc)
    dir_acc_5d = compute_directional_accuracy(slc, slc["wti_ret_5d_fwd"])
    return {
        "slice": name, "start": start, "end": end,
        "n_days": int(len(slc)),
        "coverage": coverage,
        "stability": stability,
        "directional_accuracy_5d": dir_acc_5d,
        "ic": ic_by_h,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=None,
                    help="Path to bot JSON — use its VoteConfig instead of defaults.")
    ap.add_argument("--horizon", nargs="+", type=int, default=[5, 20, 60],
                    help="Forward-return horizons (trading days) for IC.")
    ap.add_argument("--out", default="results/engine_signal_quality.json")
    args = ap.parse_args()

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    features = features.sort_values("date").reset_index(drop=True)

    if args.candidate:
        cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        genome = cand.get("genome") or cand.get("best_genome")
        vote_cfg, _ = genome_to_configs(genome)
        source = f"candidate:{Path(args.candidate).stem}"
    else:
        vote_cfg = VoteConfig()
        source = "engine v0.1 defaults"

    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left", suffixes=("", "_read"),
    )

    holdout_end = str(features["date"].max().date())
    slices = [
        slice_report(joined, "TRAIN", *TRAIN, horizons=args.horizon),
        slice_report(joined, "VALIDATION", *VAL, horizons=args.horizon),
        slice_report(joined, "HOLDOUT", HOLDOUT_START, holdout_end,
                     horizons=args.horizon),
    ]

    out = {
        "source": source,
        "horizons_days": args.horizon,
        "slices": slices,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    print(f"=== Engine signal quality — {source} ===")
    for s in slices:
        print(f"\n{s['slice']:12s}  {s['start']} -> {s['end']}   n_days={s['n_days']}")
        print(f"  coverage={s['coverage']:.1%}  stability={s['stability']:.1%}")
        da = s["directional_accuracy_5d"]
        wr = f"{da['directional_wr']:.1%}" if da["directional_wr"] is not None else "N/A"
        print(f"  5d directional accuracy (WR-analog): {wr}  "
              f"n_directional={da['n_directional']}  flat_rate={da['flat_rate']:.1%}")
        print("  IC (Spearman signed_conf vs fwd_ret):")
        for k, v in s["ic"].items():
            ic = f"{v['ic']:+.4f}" if v["ic"] is not None else "  N/A"
            print(f"    {k:8s} = {ic}  (n={v['n']})")

    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
