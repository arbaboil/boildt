# Daily-cadence performance summary (post ATR-fix)

Session 1 flagged daily cadence as `shadow_only=true` because Sharpe CI
crossed zero on TRAIN. That was on ATR-buggy data. Rerun on fixed data:

## Engine v0.1 hand-picked defaults, daily cadence, TRAIN 2001-2018

| Metric | Value | v0.1.0 gate |
|---|---|---|
| n_trades | 495 | ≥100 ✓ |
| Directional WR | 40.2% | ≥50% ✗ |
| mean R (net) | +0.134 | — |
| total R | +66.49 | — |
| Sharpe | +0.50 CI [+0.03, +0.96] | CI > 0 ✓ |
| Expectancy CI | [+0.007, +0.265] | (v0.2.0 g2a) ✓ |
| Permutation p | 0.018 | ≤0.05 ✓ |
| max_dd | 26.3R | ≤15R ✗ |

Result: **daily engine passes 3 of 5 numeric gates** (up from 0 on buggy
data). Still fails WR and max_dd.

## Bot v3 seed 7 genome forced to daily cadence

| Slice | n | WR | mean R | Sharpe | Sharpe CI | max_dd | perm p |
|---|---|---|---|---|---|---|---|
| TRAIN 2006-2018 | 354 | 32% | +0.81 | +1.43 | [+0.95, +1.89] | 18.4R | 0.000 |
| VALIDATION 2019-2023 | 129 | 34% | +1.08 | +1.75 | [+0.81, +2.63] | 11.4R | 0.000 |
| HOLDOUT 2024→ | 81 | 33% | +0.68 | +1.32 | [+0.37, +2.11] | 11.7R | 0.011 |

Notes:
- Sharpe CI positive on all three slices.
- TRAIN max_dd (18.4R) fails Gate 5 — daily fires more often and
  accumulates larger drawdowns in R. VAL + HOLDOUT max_dd both < 15R.
- All permutation p-values < 0.05.

## Ship stance

- **Weekly is the primary ship cadence** (Sharpe +1.60 CI [+1.14, +2.04]
  on TRAIN, DD 10.7R). Bot v3 seed 7 ships in weekly mode.
- **Daily is a shadow-only brief**, marked `shadow_only=true` in
  emitted daily-brief.json. Members can see the daily read but the
  simulator's daily variant is not the ship candidate.
- Under PROTOCOL v0.2.0 (expectancy-CI, no WR gate), the daily engine
  would additionally pass Gate 2a on TRAIN (expectancy CI-low +0.007 > 0)
  — but still fails max_dd, so it remains shadow-only.
