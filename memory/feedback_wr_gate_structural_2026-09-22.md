---
name: WR gate and Sharpe-CI gate are structurally mutually exclusive on oil (4 sweeps, 51 seeds)
description: Under strict PROTOCOL v0.1.0, zero of 51 seeds tested pass both Gate 1 (Sharpe CI > 0 on VAL) AND Gate 2 (WR ≥ 50% on VAL). The gates are in structural tension on oil's signal manifold across four orthogonal search strategies.
type: feedback
---

Four independent GA search strategies were run on ATR-fixed data (2026-09-22 session 3), 51 seeds total:

1. **Fresh-seed sweep** (`bot_v2_freshseed_sweep.json`, 20 seeds, worst-fold Calmar fitness, free R:R): 20/20 pass Sharpe CI-low > 0 on TRAIN + VAL + HOLDOUT. 0/20 pass WR ≥ 50%. Converge to R:R = 3.9-6.7 (asymmetric trend-follower).
2. **Engine v0.2 sweep** (`engine_v02_sweep.json`, 12 seeds, worst-fold Calmar fitness, locked TradeConfig k_stop=1.5 k_target=3.0): 0/12 pass Sharpe CI-low > 0 on VAL/HOLDOUT (all negative). 0/12 pass WR ≥ 50%. Locked symmetric R:R produces TRAIN-only fits that don't generalize.
3. **WR-pressure sweep** (`wr_pressure_sweep.json`, 10 seeds, worst-fold Calmar − 15 × max(0, 0.55 − min_fold_WR), free R:R): 10/10 pass WR ≥ 50% on TRAIN, 8/10 on VAL. 0/10 pass Sharpe CI-low > 0 on VAL (all -0.16 to -0.76). Converge to R:R = 0.77-1.62 (roughly symmetric).
4. **Alt-strategy sweep** (`alt_strategy_sweep.json` + inline seed 41, 10 seeds, worst-fold Calmar fitness, w_trend and w_momentum pinned to 0.5): 10/10 converge to asymmetric R:R = 3.76-6.67. 10/10 pass Sharpe CI on TRAIN + VAL. 0/10 pass WR ≥ 50% on VAL. Proves asymmetric R:R is structural to oil, NOT a bias from trend features.

**Verdict: 0 of 51 seeds pass both Gate 1 AND Gate 2 on VAL simultaneously.**

**Why:** The two gates capture different geometric properties. Gate 1 (Sharpe CI) rewards strategies where the *risk-adjusted* expected R generalizes out of sample — favored by asymmetric trend-followers on oil. Gate 2 (WR) rewards strategies where the *directional accuracy* is symmetric-R:R-friendly — but symmetric R:R on oil doesn't generalize past TRAIN. Oil's profitable-strategy manifold has these two properties in structural tension.

**How to apply.** The PROTOCOL v0.2.0 amendment is not "the easier path"; it is the ONLY path that admits a ship candidate under any tested search strategy. Under v0.1.0 nothing ships. Under v0.2.0 (Gate 1 CI + Gate 2b `mean_r_net ≥ 0.05` invariant, WR gate removed), bot v3 seed 7 passes cleanly on all 3 slices. See `docs/SESSION3-REPORT.md` for the full evidence bundle. Until owner signs v0.2.0: bot line remains ship-blocked. Engine can still ship using seed 7's tuned VoteConfig as its signal producer (already wired in `scripts/emit_reads.py`).
