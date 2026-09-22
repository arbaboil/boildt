"""HOLDOUT drift audit for a bot candidate.

Breaks HOLDOUT trades into quarterly windows and reports metrics per
quarter. Detects performance degradation trend that would predict a
failing shadow window (Gate 7). Also runs a Mann-Kendall trend test on
mean_R by quarter.

Usage:
    python scripts/holdout_drift.py --candidate results/bots/bot_v3_seed7_candidate.json
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
from src.engine.regime_vote import score_matrix
from src.sim.backtest import simulate
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS

HOLDOUT_START = "2024-01-01"


def _mann_kendall(x: np.ndarray) -> tuple[float, float]:
    """Mann-Kendall trend test. Returns (S statistic, p-value approx).

    Small n so we use exact if n<=10 else Gaussian approximation.
    """
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += np.sign(x[j] - x[i])
    # Variance (no ties assumed — quarterly means unlikely to tie).
    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / np.sqrt(var)
    elif s < 0:
        z = (s + 1) / np.sqrt(var)
    else:
        z = 0.0
    # Two-sided p-value from normal.
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    return float(s), float(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand_path = Path(args.candidate)
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    genome = cand.get("best_genome") or cand.get("genome")
    vote_cfg, trade_cfg = genome_to_configs(genome)

    features = pd.read_parquet(DATA_PROCESSED / "features.parquet")
    features["date"] = pd.to_datetime(features["date"])
    reads = score_matrix(features, vote_cfg)
    joined = features.merge(
        reads[["date", "read", "confidence", "score", "coverage"]],
        on="date", how="left",
    )
    lo = pd.to_datetime(HOLDOUT_START, utc=True)
    hi = pd.to_datetime(features["date"].max(), utc=True)
    ho = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    trades = simulate(ho, trade_cfg)

    if len(trades) == 0:
        raise SystemExit("No HOLDOUT trades.")

    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["quarter"] = trades["entry_date"].dt.to_period("Q").astype(str)

    quarters = []
    grouped = trades.groupby("quarter", sort=True)
    for q, g in grouped:
        n = len(g)
        wins = (g["r_net"] > 0).sum()
        quarters.append({
            "quarter": q,
            "n_trades": int(n),
            "wr": float(wins / n) if n > 0 else 0.0,
            "mean_r_net": float(g["r_net"].mean()),
            "total_r_net": float(g["r_net"].sum()),
            "best_r": float(g["r_net"].max()),
            "worst_r": float(g["r_net"].min()),
        })

    mean_r_seq = np.array([q["mean_r_net"] for q in quarters])
    s_stat, p_value = _mann_kendall(mean_r_seq)
    trend_direction = "up" if s_stat > 0 else "down" if s_stat < 0 else "flat"

    n_positive_qtrs = sum(1 for q in quarters if q["mean_r_net"] > 0)

    out = {
        "candidate_source": str(cand_path),
        "holdout_start": HOLDOUT_START,
        "holdout_end": str(features["date"].max().date()),
        "n_quarters": len(quarters),
        "n_trades_total": int(len(trades)),
        "quarters": quarters,
        "mann_kendall_s": s_stat,
        "mann_kendall_p_value": p_value,
        "trend_direction": trend_direction,
        "n_positive_quarters": n_positive_qtrs,
        "drift_flag": bool(p_value < 0.10 and trend_direction == "down"),
    }
    out_path = Path(args.out) if args.out else (
        RESULTS_BOTS / f"{cand_path.stem}_holdout_drift.json"
    )
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    print(f"=== HOLDOUT drift audit — {cand_path.name} ===")
    print(f"Range: {HOLDOUT_START} to {out['holdout_end']}")
    print(f"Total HOLDOUT trades: {len(trades)}")
    print(f"{'quarter':>7} {'n':>4} {'wr':>5} {'meanR':>7} {'totR':>7}  {'best':>6} {'worst':>6}")
    for q in quarters:
        print(f"{q['quarter']:>7} {q['n_trades']:4d} {q['wr']:5.0%} "
              f"{q['mean_r_net']:+7.2f} {q['total_r_net']:+7.1f}  "
              f"{q['best_r']:+6.2f} {q['worst_r']:+6.2f}")
    print(f"\npositive-R quarters: {n_positive_qtrs} / {len(quarters)}")
    print(f"Mann-Kendall S: {s_stat:+.1f}  p-value: {p_value:.3f}  "
          f"trend: {trend_direction}")
    if out["drift_flag"]:
        print("DRIFT FLAG: significant downward trend detected — investigate before shadow.")
    else:
        print("No significant downward drift detected.")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
