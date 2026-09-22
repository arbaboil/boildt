"""Monte Carlo forward-path simulation for a bot candidate.

Takes the empirical distribution of a candidate's per-trade R values on
TRAIN + VAL + HOLDOUT (the full sample), then resamples with replacement
into N synthetic equity curves of a target length. Reports CIs on
final-R, max-DD, terminal drawdown, probability of >X drawdown, etc.

Design notes:
  - Resamples per-trade (block=1). If per-trade autocorrelation is
    non-trivial we would use blocks; permutation test p ≈ 0 for seed 7
    suggests near-zero autocorrelation, so block=1 is defensible.
  - Runs `horizon` trades per path — chosen so path length matches a
    ~year of live trading. Seed 7 fires roughly 40 trades / year weekly,
    so horizon=40 corresponds to 1 year.
  - Reports probability of ruin under conservative capital assumption:
    with 1R = 1% of capital, ruin = cumulative drawdown > 50R.
  - Also stress-tests: subtract an extra 5 bps slippage per trade
    (worst-case widening under physical-crude realities).

Usage:
    python scripts/monte_carlo_paths.py --candidate results/bots/bot_v3_seed7_candidate.json \
                                        --horizon 40 --n-paths 5000
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
from src.sim.backtest import simulate
from src.util.paths import DATA_PROCESSED, RESULTS_BOTS


RUIN_THRESHOLD_R = 50.0   # cumulative drawdown that we call "ruin" (assumes 1R = 1% of capital)
STRESS_SLIPPAGE_BPS = 5.0


def _trades_for_candidate(cand_path: Path) -> pd.DataFrame:
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
    lo = pd.to_datetime("2006-01-01", utc=True)
    hi = pd.to_datetime(features["date"].max(), utc=True)
    slc = joined[(joined["date"] >= lo) & (joined["date"] <= hi)].reset_index(drop=True)
    return simulate(slc, trade_cfg)


def _path_stats(r_seq: np.ndarray) -> dict:
    equity = np.cumsum(r_seq)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    return {
        "final_r": float(equity[-1]),
        "max_dd": float(dd.max()),
        "worst_r_bar": float(r_seq.min()),
        "best_r_bar": float(r_seq.max()),
        "final_equity_curve_last5": [float(x) for x in equity[-5:]],
    }


def monte_carlo(trades: pd.DataFrame, horizon: int, n_paths: int,
                seed: int = 1234, stress_bps: float = 0.0) -> dict:
    r = trades["r_net"].to_numpy(dtype=float)
    # 1R value in $-terms: at 10 bps per trade this reads to 0.0001 * entry_px
    # We deduct stress_bps additional cost as a fraction of 1R by using the
    # ratio of cost/(k_stop*atr). Approximate as `stress_bps / 100 R` in
    # aggregate (conservative — assumes 1R ≈ 100 bps of the trade's notional).
    if stress_bps > 0:
        r = r - (stress_bps / 100.0)

    rng = np.random.default_rng(seed)
    finals = np.empty(n_paths)
    max_dds = np.empty(n_paths)
    ruined = 0

    for i in range(n_paths):
        picks = rng.integers(0, len(r), size=horizon)
        seq = r[picks]
        stats = _path_stats(seq)
        finals[i] = stats["final_r"]
        max_dds[i] = stats["max_dd"]
        if max_dds[i] >= RUIN_THRESHOLD_R:
            ruined += 1

    def _pct(arr, p):
        return float(np.percentile(arr, p))

    return {
        "horizon_trades": horizon,
        "n_paths": n_paths,
        "stress_slippage_bps_extra": stress_bps,
        "trades_sampled_from": int(len(r)),
        "mean_r_per_trade_after_stress": float(r.mean()),
        "final_r": {
            "median": _pct(finals, 50),
            "p05": _pct(finals, 5),
            "p25": _pct(finals, 25),
            "p75": _pct(finals, 75),
            "p95": _pct(finals, 95),
            "mean": float(finals.mean()),
        },
        "max_dd_r": {
            "median": _pct(max_dds, 50),
            "p75": _pct(max_dds, 75),
            "p95": _pct(max_dds, 95),
            "p99": _pct(max_dds, 99),
            "max": float(max_dds.max()),
        },
        "prob_positive_final_r": float((finals > 0).mean()),
        "prob_final_r_ge_10": float((finals >= 10).mean()),
        "prob_final_r_ge_30": float((finals >= 30).mean()),
        "prob_max_dd_ge_15": float((max_dds >= 15.0).mean()),
        "prob_max_dd_ge_25": float((max_dds >= 25.0).mean()),
        "prob_ruin": ruined / n_paths,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--horizon", type=int, default=40,
                    help="Trades per synthetic path (default 40 ≈ 1 year weekly).")
    ap.add_argument("--n-paths", type=int, default=5000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cand_path = Path(args.candidate)
    trades = _trades_for_candidate(cand_path)
    print(f"Candidate has {len(trades)} historical trades on 2006-now.")

    baseline = monte_carlo(trades, args.horizon, args.n_paths, seed=1234)
    stress = monte_carlo(trades, args.horizon, args.n_paths, seed=1234,
                         stress_bps=STRESS_SLIPPAGE_BPS)

    out = {
        "candidate_source": str(cand_path),
        "n_historical_trades": int(len(trades)),
        "baseline": baseline,
        "stress_extra_5bps": stress,
    }

    out_path = Path(args.out) if args.out else (
        RESULTS_BOTS.parent / "monte_carlo" / f"{cand_path.stem}_mc.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    def _print(name: str, r: dict) -> None:
        print(f"\n=== {name} ===")
        print(f"  horizon:                     {r['horizon_trades']} trades  "
              f"({r['n_paths']} paths)")
        print(f"  mean R per trade (after stress): {r['mean_r_per_trade_after_stress']:+.3f}")
        print(f"  final_R median:              {r['final_r']['median']:+.1f}")
        print(f"  final_R p05..p95:            [{r['final_r']['p05']:+.1f}, "
              f"{r['final_r']['p95']:+.1f}]")
        print(f"  P(final > 0):                {r['prob_positive_final_r']:.1%}")
        print(f"  P(final >= +10R):            {r['prob_final_r_ge_10']:.1%}")
        print(f"  P(final >= +30R):            {r['prob_final_r_ge_30']:.1%}")
        print(f"  max_dd median / p95 / p99:   {r['max_dd_r']['median']:.1f}R / "
              f"{r['max_dd_r']['p95']:.1f}R / {r['max_dd_r']['p99']:.1f}R")
        print(f"  P(max_dd >= 15R):            {r['prob_max_dd_ge_15']:.1%}")
        print(f"  P(max_dd >= 25R):            {r['prob_max_dd_ge_25']:.1%}")
        print(f"  P(ruin, dd >= {RUIN_THRESHOLD_R:.0f}R):        {r['prob_ruin']:.2%}")

    _print("BASELINE (empirical costs)", baseline)
    _print("STRESS (+5 bps slippage per trade)", stress)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
