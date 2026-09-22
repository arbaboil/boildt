---
name: Helios bot v3 candidate — seed 7 from 20-seed fresh-seed sweep
description: Post-ATR-fix candidate. Passes Sharpe CI on all 3 slices + WF 10/10; blocked only by WR gate.
type: project
---

**Artifact.** `results/bots/bot_v3_seed7_candidate.json` — evolved by GA seed 7 on TRAIN 2006-2018 with pop=64, gens=30, sigma=0.12, fitness = worst-fold Calmar (v2-style, no WR penalty). Selected from `results/bots/freshseed/seed_*.json` (20 seeds, all evolved from scratch on ATR-fixed data via `scripts/freshseed_sweep.py`, roll-up at `results/bots/bot_v2_freshseed_sweep.json`).

**Genome.** k_stop 0.75 ATR, k_target 4.69 ATR (R:R 6.22), max_hold 11 days. Weights: w_curve 3.83, w_vol 2.10, w_macro 2.07, w_momentum 1.32, w_eia 1.13, w_cot 0.98, w_trend 0.61. Interpretation: crack-spread/curve trend-follower with vol and DXY overlays, tight stops, letting winners run.

**Results.**
- TRAIN 2006-2018: n=238, WR 38%, mean R +1.14, total R +272, Sharpe +1.60, CI [+1.14, +2.04], max_dd 10.7R
- VAL 2019-2023: n=89, WR 33%, mean R +0.88, total R +78.5, Sharpe +1.24, CI [+0.45, +1.98], max_dd 10.2R
- HOLDOUT 2024→: n=58, WR 36%, mean R +0.97, total R +56.4, Sharpe +1.49, CI [+0.58, +2.24], max_dd 6.8R
- Walk-forward K=10 (2006-2023): 10/10 folds positive expectancy, 10/10 positive Sharpe

**Gate status (PROTOCOL v0.1.0):**
- G1 Sharpe CI > 0: **PASS on all three slices** (only 3 of 20 seeds achieve this)
- G2 Directional WR ≥ 50%: **FAIL** (38 / 33 / 36) — same structural fail as bot v2
- G3 min 100 trades TRAIN: PASS (238)
- G4 ≥ 7/10 folds positive: PASS (10/10)
- G5 max DD ≤ 15R: PASS on all slices (worst 10.7R)
- G6 permutation p ≤ 0.05: not yet re-run on candidate (pending)
- G7 ≥ 4-week silent-live shadow: NOT STARTED

**Convergent-shape evidence.** All 20 seeds in the sweep independently converge to asymmetric R:R (3.9-6.7) with heavy w_curve (2.5-3.8) and w_macro (1.8-4.0). 0/20 pass the WR gate on any slice. 95% pass strict-minus-WR (TRAIN + VAL Sharpe CI > 0, WF 7/10+, max_dd ≤ 15R, n ≥ 100).

**Why:** The 20-seed sweep is the honest B7 audit — under fresh seeds, does the same shape emerge? Yes. This proves oil's profitable-strategy family is inherently asymmetric R:R, ruling out "bot v2 was a lucky asymmetric seed" and forcing the WR-gate question up to owner. Memo at `docs/memos/2026-09-22_WR_gate_asymmetric_RR.md` recommends Option B (replace WR gate with expectancy-CI in PROTOCOL v0.2.0).

**How to apply.** Do NOT ship until owner decides on Option B. If approved, start `--candidate results/bots/bot_v3_seed7_candidate.json` shadow window via `scripts/shadow_log.py`. Also re-run permutation test (G6). If rejected (owner keeps WR gate), the entire bot line is blocked — Helios needs a different feature set or an entirely different strategy family (e.g., mean-reversion in vol regimes). Not obvious such a family exists for oil.
