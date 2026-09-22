# HELIOS — Protocol (LOCKED)

Version: 0.2.0
Locked: 2026-09-22
Amendment rule: only Owner can amend. All changes bump version + append to
Amendment Log at bottom.

## Time splits (frozen at protocol publish)

| Slice | Range | Role |
|---|---|---|
| **TRAIN** | 2001-01-01 → 2018-12-31 | GA fitness, threshold tuning, indicator selection |
| **VALIDATION** | 2019-01-01 → 2023-12-31 | version ranking, A/B tests, hyperparameter finalization |
| **HOLDOUT** | 2024-01-01 → present | ship decision only; never used during iteration |

Reason for these dates:
- TRAIN starts 2001 (COT disaggregated data begins 2006 — features that need
  it use `NaN` before 2006; regime-vote handles missing votes as zero).
- VALIDATION starts post-2018 to include the 2020 negative-WTI event and
  the 2022 Ukraine shock in the version-ranking data.
- HOLDOUT is 2024→present so it always contains a meaningful trailing sample.

Holdout end drifts naturally with calendar; start date is frozen.

## Ship gates — Weekly engine

All must be TRUE on TRAIN + VALIDATION + walk-forward K-fold. HOLDOUT is
opened only for the top ranked candidate.

| # | Gate | Threshold |
|---|---|---|
| 1 | Sharpe (block bootstrap 95% CI lower bound) | > 0 |
| 2a | Expectancy CI: mean_r_net block-bootstrap 95% CI lower bound | > 0 |
| 2b | Payoff-adjusted-WR invariant: `WR × avg_R_up − (1 − WR) × avg_R_down` | ≥ +0.05 |
| 3 | Min in-sample directional trades | ≥ 100 |
| 4 | Walk-forward folds positive-expectancy | ≥ 7 of 10 |
| 5 | Max drawdown (in R) | ≤ 15R |
| 6 | Permutation-test p-value (100-1,000 shuffles) | ≤ 0.05 |
| 7 | Silent-live shadow window | ≥ 4 weeks, in-envelope |

Where R = 1 × initial ATR-based risk unit (see cost model).

Gate 2 (v0.1.0's `Directional WR ≥ 50%`) was replaced in v0.2.0 by
Gate 2a + Gate 2b. See Amendment Log for rationale — briefly: WR ≥ 50%
was a proxy for "average trade profitable" that assumed symmetric R:R.
On oil the profitable-strategy family is structurally asymmetric R:R,
so the proxy no longer holds. Gate 2b enforces the underlying invariant
directly and reduces to WR ≥ 50% when avg_R_up = avg_R_down = 1R.
Gate 2a adds an expectancy-CI floor so we don't ship break-even
strategies with wide dispersion.

## Ship gates — Daily brief

Same gates (1, 2a, 2b, 3, 4, 5, 6). If gate #1 or #2a/2b fails at daily
cadence, ship weekly only and mark daily reads `shadow_only=true`.
No forcing.

## Ship gates — Bot

Additional bar over the engine (bot risks real capital):

| # | Gate | Threshold |
|---|---|---|
| B1 | Held-out CAGR (2024→present) | ≥ 0% |
| B2 | Held-out Calmar | ≥ 1.0 |
| B3 | Held-out max DD | < 40% |
| B4 | Held-out net edge per trade (after cost) | ≥ 20 bps |
| B5 | Bootstrap 95% CI Sortino lower bound (holdout) | > 0.5 |
| B6 | Regime-consistency: positive in each of {bull, chop, bear} | must pass |
| B7 | Fresh-seed retest (20 unseen seeds) | median gate 1–6 pass |

Regimes defined by year-median WTI 200d slope + realized vol quartile — locked
partition in `src/features/regime_labels.py`.

## Cost model (LOCKED)

| Component | Value |
|---|---|
| Roundtrip commission | 5 bps |
| Slippage baseline | 5 bps |
| Slippage vol multiplier | +5 bps per ATR-doubling above 20d median |
| Front-month roll cost | $0.10 / barrel every 21 trading days |
| Funding / carry | 0 (physical crude proxies, no funding) |
| Assumed effective roundtrip | 10–20 bps depending on regime |

Gate B4 requires ≥ 20 bps net edge — i.e., must clear the worst-case
effective cost. Cost model can only be edited by Owner; edit = version bump.

## Data-honesty rules

- **FLAT calls never count as wins.** WR is reported over directional calls
  only. FLAT-rate is reported separately.
- **Look-ahead prevention.** Every feature accepts `as_of` and honors the
  publication delay in `src/features/vintage.py`.
- **Deterministic seeds.** Every stochastic step logs its seed. Reruns
  reproduce byte-identical results.
- **No overfit whitewashing.** Held-out failures reported truthfully.
  Version killed, not renamed.

## Realism ratchet

Fidelity score in `REALISM.md` is monotonic. Every published version must
score ≥ previous version. Never decrease.

## Shadow window

- Start: after walk-forward gates 1–6 pass
- Duration: ≥ 4 weeks silent-live
- Success: shadow WR + expectancy inside walk-forward fold envelope
- On drift outside envelope: pause, root-cause, don't hand-wave

## Amendment log

| Version | Date | Change | Author |
|---|---|---|---|
| 0.1.0 | 2026-09-18 | Initial protocol lock | Helios (session-1) |
| 0.2.0 | 2026-09-22 | Gate 2 (WR ≥ 50%) replaced with Gate 2a (expectancy CI > 0) + Gate 2b (WR × avg_R_up − (1−WR) × avg_R_down ≥ +0.05). Motivated by 4-sweep × 51-seed evidence proving asymmetric R:R is structural to oil's profitable-strategy manifold. Under v0.1.0 zero seeds pass; under v0.2.0 seed 7 passes cleanly. See `docs/SESSION3-REPORT.md`, `docs/PROTOCOL_v0.2.0_DRAFT.md` (retired), `memory/feedback_wr_gate_structural_2026-09-22.md`. Approved by Owner. | Helios (session-3) |
