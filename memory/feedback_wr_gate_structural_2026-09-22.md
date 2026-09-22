---
name: WR gate structurally unreachable for oil (session 2, 20-seed sweep)
description: 20 independent GA seeds all converge to asymmetric R:R. WR ≥ 50% is not reachable for oil under current features.
type: feedback
---

Fresh-seed sweep of 20 evolved bots on ATR-fixed data (bot_v2_freshseed_sweep.json, 2026-09-22): **0/20 seeds achieve WR ≥ 50% on TRAIN or VAL.** All 20 independently converge to R:R = 3.9–6.7, heavy on w_curve (2.5–3.8) and w_macro (1.8–4.0), tight stops (0.75–0.85 ATR), large targets (3.4–5.0 ATR).

95% of seeds pass strict-minus-WR (TRAIN + VAL Sharpe CI > 0 + WF ≥ 7/10 + max_dd ≤ 15R + n ≥ 100). Median TRAIN Sharpe CI-low +1.07, median VAL Sharpe CI-low +0.44. Real edge, wrong shape for a 50%-WR gate.

**Why:** The PROTOCOL v0.1.0 gate 2 (WR ≥ 50%) was inherited from AXIS (BTC/gold), where symmetric R:R strategies dominate. Oil's natural profitable family is asymmetric trend-follower — high avg-R payoff, sub-50% WR. Gate 2 filters out the entire oil signal family. This is not a lucky-seed artifact — it's convergent from independent seeds.

**How to apply.** Recommend owner adopt PROTOCOL v0.2.0 amendment: replace WR ≥ 50% with expectancy-CI floor (bootstrap 95% CI of mean_r_net > 0 on TRAIN + VAL) plus a "WR × avg_R_up + (1 − WR) × avg_R_down > 0" invariant (which is what WR ≥ 50% was proxying for symmetric R:R). Draft memo at `docs/memos/2026-09-22_WR_gate_asymmetric_RR.md`. Until owner amends: bot line is ship-blocked. Engine improvements (features, regime labels, EIA surprise) are independent and can continue.
