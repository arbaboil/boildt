---
name: Helios ship gates
description: Pointer to docs/PROTOCOL.md v0.1.0 — locked ship gates for Helios engine and bot
type: reference
---

Full spec at `docs/PROTOCOL.md` (v0.1.0 locked 2026-09-18). Summary:

**Weekly engine (all must pass):**
- Sharpe block-bootstrap 95% CI lower bound > 0
- Directional WR (excl FLAT) ≥ 50%
- Min 100 in-sample trades
- ≥ 7 of 10 walk-forward folds positive-expectancy
- Max DD ≤ 15R
- Permutation p ≤ 0.05
- ≥ 4-week silent-live shadow window in-envelope

**Daily brief:** same gates or `shadow_only: true`.

**Bot (extra):**
- Held-out (2024→present) CAGR ≥ 0%, Calmar ≥ 1.0, DD < 40%, net edge ≥ 20 bps
- Sortino block-bootstrap 95% CI lower bound > 0.5
- Regime-consistent (positive in bull, chop, bear)
- Fresh-seed retest: 20 unseen seeds median passes gates 1–6

Cost model locked: 5 bps commission + 5 bps slippage baseline + vol-scaled slippage + $0.10/bbl every 21 BD.

Splits frozen: TRAIN 2001-01-01→2018-12-31, VAL 2019-01-01→2023-12-31, HOLDOUT 2024-01-01→present.
