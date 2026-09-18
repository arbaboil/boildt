---
name: Helios bot v2 candidate 2026-09-18
description: First real bot candidate — 10/10 K-fold folds positive but fails WR ≥50% gate
type: project
---

**Artifact.** `results/bots/bot_v2_seed42.json` (evolved), `results/bots/bot_v2_validation.json` (TRAIN/VAL/HOLDOUT), `results/walkforward/bot_v2_walkforward.json` (K=10).

**Evolved on:** TRAIN 2006-01-01 → 2018-12-31, 5-fold split, pop=64, gens=30, sigma=0.12, seed=42, fitness = worst-fold Calmar with MIN_ACTIVE_FOLDS_FRAC=0.8 + MIN_TRADES_TOTAL=30 + COVERAGE_PENALTY=8.

**Results (out-of-sample honest):**
- TRAIN 2006-2018: n=153, WR 44%, meanR +1.18R, Sharpe 1.42 CI [+1.02, +1.81]
- VALIDATION 2019-2023: n=56, WR 43%, meanR +0.98R, Sharpe 1.24 CI [+0.43, +2.06]
- HOLDOUT 2024-present: n=27, WR 41%, meanR +0.84R, Sharpe 1.02 CI [-0.18, +1.85]
- Walk-forward K=10 (2006-2023): **10/10 folds positive-expectancy**, 10/10 folds positive Sharpe

**Gate status:**
- G1 Sharpe CI > 0: PASS on TRAIN + VAL; HOLDOUT crosses zero (n=27 too small)
- **G2 Directional WR ≥ 50%: FAIL (~43% across all slices)**
- G3 min 100 trades: PASS (153 TRAIN)
- G4 ≥ 7/10 folds positive: PASS (10/10)
- G5 max DD ≤ 15R: PASS (5.5R on TRAIN)
- G7 shadow ≥ 4 weeks: NOT STARTED

**Evolved genome character:**
- Asymmetric R:R: k_stop 0.78 ATR (tight), k_target 5.0 ATR (max range)
- Short hold: 7 days max
- Heaviest features: macro (DXY) w=4.0, momentum w=3.8, trend w=2.1
- Turns off: vol regime (w=0.0), COT positioning (w=0.04)
- Narrow strong-conviction band (moderate 0.17, strong 0.72)
- Interpretation: DXY-informed trend follower with tight stops

**Why:** Asymmetric-R:R strategies naturally sit below 50% WR because a 1:5 R:R can be profitable at 20% WR. The FAR playbook's 50% WR gate was written for BTC/gold which typically ship 1:1 or 1:1.5 R:R geometries. Enforcing 50% here filters out a legitimate strategy shape.

**How to apply.** Do NOT ship v2 as-is (fails WR gate + no shadow). Next steps: (1) draft memo to owner on WR gate for asymmetric-R:R crude strategies; (2) fresh-seed retest per gate B7; (3) run v3 with fitness variant that rewards WR to see if 50% is reachable without wrecking expectancy; (4) start ≥4-week shadow window once a shippable variant lands.
