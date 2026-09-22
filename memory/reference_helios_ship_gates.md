---
name: Helios ship gates (PROTOCOL v0.2.0 — LOCKED)
description: Pointer to docs/PROTOCOL.md v0.2.0 — Owner-approved 2026-09-22. Gate 2 (WR ≥ 50%) retired; replaced by Gate 2a + 2b.
type: reference
---

Full spec at `docs/PROTOCOL.md` (v0.2.0 locked 2026-09-22, approved by Owner). Summary:

**Weekly engine (all must pass):**
- Gate 1: Sharpe block-bootstrap 95% CI lower bound > 0
- Gate 2a: Expectancy (mean_r_net) block-bootstrap 95% CI lower bound > 0
- Gate 2b: WR × avg_R_up − (1 − WR) × avg_R_down ≥ +0.05 (algebraically equal to mean_r_net ≥ 0.05)
- Gate 3: Min 100 in-sample trades
- Gate 4: ≥ 7 of 10 walk-forward folds positive-expectancy
- Gate 5: Max DD ≤ 15R
- Gate 6: Permutation p ≤ 0.05
- Gate 7: ≥ 4-week silent-live shadow window in-envelope

**Retired in v0.2.0:** Gate 2 (Directional WR ≥ 50%). Replaced with Gate 2a + Gate 2b after 51-seed evidence proved asymmetric R:R is structural to oil's profitable-strategy manifold. Old field retained in audit output under `g2_wr_ge_50_retired` for historical continuity only; not used in ship decisions.

**Daily brief:** same gates or `shadow_only: true`.

**Bot (extra):**
- Held-out (2024→present) CAGR ≥ 0%, Calmar ≥ 1.0, DD < 40%, net edge ≥ 20 bps
- Sortino block-bootstrap 95% CI lower bound > 0.5
- Regime-consistent (positive in bull, chop, bear)
- Fresh-seed retest: 20 unseen seeds median passes gates 1–6

Cost model locked: 5 bps commission + 5 bps slippage baseline + vol-scaled slippage + $0.10/bbl every 21 BD.

Splits frozen: TRAIN 2001-01-01→2018-12-31, VAL 2019-01-01→2023-12-31, HOLDOUT 2024-01-01→present.

**Bot v3 seed 7 status (2026-09-22):** passes strict v0.2.0 on TRAIN + VAL + HOLDOUT. Only remaining ship blocker is Gate 7 (26 of 28 shadow days remaining).
