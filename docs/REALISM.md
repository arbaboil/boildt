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

### v0.1 (scaffold — session 1, 2026-09-18)

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

### v0.2 (post-fix + full audit — session 2, 2026-09-22)

| Category | Score | Delta | Notes |
|---|---|---|---|
| Look-ahead prevention | 17 | +9 | `vintage.safe_asof` enforced in features; forward-fill lock in `build_features` respects same-day-only; 3 regression tests including `test_no_lookahead_slope_shape` |
| Fill realism | 8 | +4 | Close-to-close still, but same-day stop+target ordering documented in `backtest.py` (stop wins ties). Holiday gaps now handled via ffill on indicators, raw close preserved for gating. Intrabar still Phase 5. |
| Cost realism | 12 | +4 | Cost model vol-scaled (log2 doublings above 20d median). Stress-tested at 2x and 3x — bot v3 seed 7 maintains Sharpe CI > 0 across all slices even at 3x cost. |
| Microstructure | 3 | +1 | priceStep-style bounds enforced (0.5–1.5× price for stops, 0.5–10% ATR pct). Still no order-book depth model. |
| World-state fidelity | 12 | +6 | Pulled: FRED (WTI/Brent/DXY/real-yield/VIX/YC/INDPRO/HY_OAS), Yahoo (WTI/Brent/OVX/DXY/VIX/SP500/HO/RB/NG), CFTC COT (WTI 817 wks + Brent 240 wks), Baker Hughes. Missing: EIA (needs API key from owner), OPEC monthly PDF, GDELT, NOAA. |
| Statistical validity | 14 | +10 | Live: 5000-sample block-bootstrap CI on Sharpe + expectancy; 1000-permutation p-value on all three slices; K=10 walk-forward; 20-seed fresh-seed retest with roll-up gate rates; 10k-path Monte Carlo forward CIs with stress variant; Gate B6 regime-consistency check. Holdout locked and never touched during evolution. |
| Cross-asset correlation | 8 | +3 | DXY, VIX, real-yield-10y, INDPRO YoY, HY OAS, SP500 20d return all wired into feature matrix. Missing: ISM, China PMI, Baltic Dry Index. |
| **Total** | **74/100** | **+37** | Approaching ship floor (80). Under PROTOCOL v0.2.0 with EIA + intrabar upgrade this reaches ~85. |

### Roadmap to 80+

Original session-1 roadmap. Items marked ✓ landed in session 2.

1. ✓ **+8 look-ahead** — `vintage.safe_asof` + ffill locks + no-lookahead tests
2. **+8 fill realism** — intrabar iteration + gap-through + wick-stop (Phase 5)
3. **+3 world-state** — EIA weekly petroleum status (needs owner API key);
   OPEC + GDELT + NOAA still not pulled
4. ✓ **+4 cost realism** — vol-scaled slippage curve + 2x/3x stress tests
5. ✓ **+10 statistical validity** — walk-forward K-fold, permutation,
   block bootstrap, MC, Gate B6, HOLDOUT drift
6. **+3 cross-asset** — ISM, China PMI, Baltic Dry Index
7. **+3 microstructure** — bid-ask model, position-size impact
8. **+2 fill realism** — same-bar exit rules documented → done inline in
   `backtest.py`; regression test would nudge this to +3

Remaining path 74 → 85+:
- EIA API key: unlocks +3 world-state → 77
- Intrabar fills (Phase 5): +6 fill realism → 83
- Additional macro (ISM/PMI/BDI): +3 cross-asset → 86
- Microstructure v0.1 (spread model): +2 → 88
- Documented same-bar tests: +1 → 89

## Explicitly out of scope (documented gaps)

- Real intraday microstructure: HELIOS trades daily/weekly bars, so tick-level
  fills are not modeled. Cost model buffer covers this.
- Real-money slippage under illiquid conditions: modeled with vol-scaled
  slippage but not with historical order-book depth (no free data).
- Physical delivery risk on WTI expiry: sim assumes continuous-front
  rollover with roll-cost charge; expiry-week trades are excluded to avoid
  the 2020 negative-WTI edge case bleeding into results.

If these gaps ever become material to a shipped strategy, escalate.
