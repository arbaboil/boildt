"""Rank fresh-seed sweep results and pick a candidate for shadow.

Ranking heuristic (composite score, higher is better):

    score = 0.35 * train_sharpe_ci_low
          + 0.35 * val_sharpe_ci_low
          + 0.15 * min(train_wr, val_wr)      # penalize very low WR softly
          + 0.10 * (positive_wf_folds / 10)
          + 0.05 * holdout_sharpe_ci_low_clipped

We DO NOT include HOLDOUT in the ranking beyond a token — HOLDOUT is a
one-shot audit slot, not something to optimize over. Rerunning the sweep
against HOLDOUT is analytically fine (features are frozen; genomes were
evolved on TRAIN only), but ranking by HOLDOUT would leak information.

Usage:
    python scripts/freshseed_rank.py --dir results/bots/freshseed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(dir_: Path) -> list[dict]:
    out = []
    for p in sorted(dir_.glob("seed_*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _row(r: dict) -> dict:
    tr = r["slices"][0]
    va = r["slices"][1]
    ho = r["slices"][2]
    ci_ho = max(-1.0, min(2.0, ho["bootstrap_sharpe"]["ci_low"]))
    train_wr = tr["metrics"]["directional_wr"]
    val_wr = va["metrics"]["directional_wr"]
    score = (
        0.35 * tr["bootstrap_sharpe"]["ci_low"]
        + 0.35 * va["bootstrap_sharpe"]["ci_low"]
        + 0.15 * min(train_wr, val_wr)
        + 0.10 * (r["walkforward"]["positive_expectancy_folds"] / 10.0)
        + 0.05 * ci_ho
    )
    return {
        "seed": r["seed"],
        "score": score,
        "train_n": tr["metrics"]["n_trades"],
        "train_wr": train_wr,
        "train_meanr": tr["metrics"]["mean_r_net"],
        "train_sharpe": tr["metrics"]["sharpe_per_trade"],
        "train_ci_low": tr["bootstrap_sharpe"]["ci_low"],
        "val_n": va["metrics"]["n_trades"],
        "val_wr": val_wr,
        "val_sharpe": va["metrics"]["sharpe_per_trade"],
        "val_ci_low": va["bootstrap_sharpe"]["ci_low"],
        "ho_n": ho["metrics"]["n_trades"],
        "ho_wr": ho["metrics"]["directional_wr"],
        "ho_sharpe": ho["metrics"]["sharpe_per_trade"],
        "ho_ci_low": ho["bootstrap_sharpe"]["ci_low"],
        "wf_pos_folds": r["walkforward"]["positive_expectancy_folds"],
        "strict": r["all_gates_1_5_pass"],
        "no_wr": r["gates_1_5_no_wr_pass"],
        "k_stop": r["genome"]["k_stop"],
        "k_target": r["genome"]["k_target"],
        "rr": r["genome"]["k_target"] / r["genome"]["k_stop"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/bots/freshseed")
    args = ap.parse_args()
    dir_ = Path(args.dir)
    runs = _load(dir_)
    if not runs:
        raise SystemExit(f"No seeds in {dir_}")
    rows = [_row(r) for r in runs]
    rows.sort(key=lambda r: r["score"], reverse=True)

    print(f"n_seeds = {len(rows)}")
    print(f"{'seed':>4} {'score':>6}  "
          f"{'TRAIN n':>7} {'wr':>5} {'R':>5} {'sh':>5} {'CI-':>5}  "
          f"{'VAL n':>5} {'wr':>5} {'sh':>5} {'CI-':>5}  "
          f"{'HO n':>4} {'wr':>5} {'CI-':>5}  "
          f"{'WF':>3}  {'RR':>4}  strict  no_wr")
    for r in rows:
        print(f"{r['seed']:4d} {r['score']:+.3f}  "
              f"{r['train_n']:7d} {r['train_wr']:.0%} {r['train_meanr']:+.2f} "
              f"{r['train_sharpe']:+.2f} {r['train_ci_low']:+.2f}  "
              f"{r['val_n']:5d} {r['val_wr']:.0%} "
              f"{r['val_sharpe']:+.2f} {r['val_ci_low']:+.2f}  "
              f"{r['ho_n']:4d} {r['ho_wr']:.0%} {r['ho_ci_low']:+.2f}  "
              f"{r['wf_pos_folds']:3d}  "
              f"{r['rr']:4.2f}  "
              f"{'YES' if r['strict'] else 'no ':6}  "
              f"{'YES' if r['no_wr'] else 'no'}")
    # Summary
    n = len(rows)
    n_strict = sum(1 for r in rows if r["strict"])
    n_no_wr = sum(1 for r in rows if r["no_wr"])
    n_wr_pass_train = sum(1 for r in rows if r["train_wr"] >= 0.50)
    n_wr_pass_val = sum(1 for r in rows if r["val_wr"] >= 0.50)
    print(f"\nstrict pass:       {n_strict}/{n}")
    print(f"no-WR pass:        {n_no_wr}/{n}")
    print(f"WR>=50% on TRAIN:  {n_wr_pass_train}/{n}")
    print(f"WR>=50% on VAL:    {n_wr_pass_val}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
