# HELIOS — Realism / Fidelity Score

Ratchet rule: fidelity score is monotonic. Never decreases version to version.
Every ship-ready version must clear the previous score.

## Category weights (0–100 total)

| Category | Weight |
|---|---|
| Look-ahead prevention | 20 |
| Fill realism (intrabar, gap, slippage) | 15 |
| Cost realism (commission, roll, slippage vol-scaling) | 15 |
| Microstructure (impact, liquidity) | 10 |
| World-state fidelity (all inputs bot sees exist historically) | 15 |
| Statistical validity (seeds, K-fold, holdout lock, permutation) | 15 |
| Cross-asset correlation (macro, USD, VIX) | 10 |

Ship floor: 80/100. Quant-fund standard: 90/100.

## Version log

### v0.1 (scaffold — this session)

| Category | Score | Notes |
|---|---|---|
| Look-ahead prevention | 8 | `as_of` design present but not yet enforced in every feature |
| Fill realism | 4 | Close-to-close in Phase 3; intrabar upgrade in Phase 5 |
| Cost realism | 8 | Cost model locked in PROTOCOL; not yet vol-scaled |
| Microstructure | 2 | Not modeled yet |
| World-state fidelity | 6 | Price + FRED + Yahoo present; EIA/COT/OPEC still to pull |
| Statistical validity | 4 | Bootstrap + K-fold spec written; not run |
| Cross-asset correlation | 5 | DXY + VIX + real yields in schema, joined |
| **Total** | **37/100** | Scaffold. Not shippable. |

### Roadmap to 80+

Ordered by effort / impact ratio:

1. **+8 look-ahead** — wire `safe_asof(source, date)` into every feature
2. **+8 fill realism** — intrabar iteration + gap-through + wick-stop
3. **+8 world-state** — pull EIA + COT + OPEC + Baker Hughes + GDELT + NOAA
4. **+7 cost realism** — vol-scaled slippage curve
5. **+7 statistical validity** — walk-forward K-fold, permutation test, block bootstrap
6. **+5 cross-asset** — additional macro (ISM, INDPRO, credit spread)
7. **+3 microstructure** — bid-ask model, position-size impact
8. **+2 fill realism** — same-bar exit rules exactly documented

Total roadmap: +48 → 85/100 target for v0.5 (ship candidate).

## Explicitly out of scope (documented gaps)

- Real intraday microstructure: HELIOS trades daily/weekly bars, so tick-level
  fills are not modeled. Cost model buffer covers this.
- Real-money slippage under illiquid conditions: modeled with vol-scaled
  slippage but not with historical order-book depth (no free data).
- Physical delivery risk on WTI expiry: sim assumes continuous-front
  rollover with roll-cost charge; expiry-week trades are excluded to avoid
  the 2020 negative-WTI edge case bleeding into results.

If these gaps ever become material to a shipped strategy, escalate.
