# Memo — EIA-aware GA sweep overfits HOLDOUT

**From:** Helios
**To:** Owner
**Date:** 2026-09-22
**Status:** Science finding + v0.3.0 backlog input
**Bearing on ship:** None (seed 7 remains ship candidate)

## TL;DR

Ran a fresh-seed GA sweep (10 seeds, seeds 51-60) with the newly-wired
EIA features included. All 10 seeds look **better than seed 7 on TRAIN
+ VAL** but **fail Gate 1 (Sharpe CI-low > 0) on HOLDOUT.** Seed 7,
tuned without EIA, was actually already the right ship candidate.

Do not swap. Seed 7 ships as planned on 2026-10-20.

## Data

| Seed | TR CIlo | VAL CIlo | HO CIlo | v0.2.0 |
|---|---|---|---|---|
| 7 (SHIP) | +1.14 | +0.43 | +0.61 | PASS |
| 51 | +1.34 | +1.11 | **−1.47** | FAIL |
| 52 | +1.43 | +0.93 | **−1.89** | FAIL |
| 53 | +1.41 | +0.53 | **−0.42** | FAIL |
| 54 | +1.52 | +0.91 | **−0.58** | FAIL |
| 55 | +1.37 | +0.53 | **−1.67** | FAIL |
| 56 | +1.55 | +0.73 | **−1.03** | FAIL |
| 57 | +1.42 | +0.73 | **−1.06** | FAIL |
| 58 | +1.40 | +0.91 | **−0.68** | FAIL |
| 59 | +1.37 | +0.71 | **−0.17** | FAIL |
| 60 | +1.28 | +0.67 | **−0.86** | FAIL |

All 10 look better than seed 7 on TRAIN + VAL (Sharpe CI-low +1.28 to
+1.55 on TRAIN vs seed 7's +1.14). But **every single seed goes
negative on HOLDOUT.**

## Why

The GA optimizes worst-fold Calmar on TRAIN K-folds. With the new EIA
features (`eia_stocks_surprise`, `eia_refutil_z`, `eia_crude_stocks_wchg`),
the search space has 3 more knobs to turn. The GA finds vote weights
that leverage the EIA signal on 2006-2023 data. But EIA's predictive
value on 2024-2026 appears meaningfully different — probably because:

1. **Post-COVID inventory patterns changed.** SPR release/refill cycles
   dominated 2022-2024 in ways the 5y seasonal-median baseline hasn't
   normalized yet.
2. **Small-sample HOLDOUT (54-65 trades).** Statistical significance
   is fragile; the CI wobbles more with fewer trades.
3. **EIA release-time noise.** Weekly releases at Wed 10:30 ET create
   short-lived spikes that a GA can memorize in-sample without them
   being persistent structural signal.

## Discipline validated

This is exactly why PROTOCOL locks HOLDOUT untouched during iteration.
The GA would have chosen any of seeds 51-60 as "better than seed 7"
based on TRAIN + VAL alone. HOLDOUT catches the overfit.

Seed 7 was tuned without EIA and generalizes to HOLDOUT cleanly. The
EIA feature is helpful *as a rare input* (seed 7 gives it small weight
in its VoteConfig) but destructive as a *primary driver* (which is
what the GA does when the fitness function rewards TRAIN performance).

## Ship decision

**No change.** Seed 7 is the ship candidate. Its `w_eia` in the genome
is essentially unused, which is now confirmed to be the right choice.

## v0.3.0 backlog updates

- **Do NOT re-tune seed 7 on EIA-included features.** Any new-feature
  retune must be validated with a held-out HOLDOUT check *before*
  swapping.
- **Consider regime-conditional EIA weighting.** Maybe EIA helps in
  low-vol regimes but adds noise in shock periods (SPR events).
- **Wait for more HOLDOUT trades.** Once 2024-2027 accumulates 100+
  trades, the CI stability will improve and this test can be re-run.
- **Alternative EIA feature engineering.** Instead of raw stocks
  surprise, try 4-week rolling average or trailing-year regime-relative
  z-score. These would smooth the release-time noise.

## Artifact locations

- Raw seeds: `results/bots/freshseed/seed_051.json` – `seed_060.json`
- Summary: `results/bots/bot_v3_eia_sweep.json`
- Comparison against seed 7 baseline: `results/bots/bot_v3_seed7_candidate_audit.json`
