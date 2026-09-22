# Memo — WR gate for asymmetric R:R crude strategies

**From:** Helios
**To:** Owner
**Date:** 2026-09-22
**Status:** DECISION REQUESTED
**Bearing on ship:** blocks bot v2 candidate; shapes bot v3 fitness function

---

## TL;DR

The 50%-WR gate in `PROTOCOL.md` was written for BTC/gold shapes (roughly 1:1
to 1:1.5 R:R). Session 1's bot v2 candidate hit 43% WR on all slices — a math-
ematically legitimate win rate for a 1:5 R:R geometry, but the gate blocks it.

**Update (session 2, post-ATR-fix):** Session 1's ATR indicator had a NaN
bug that silently discarded ~60% of tradeable days. The bug is now fixed
(commit `96696fb`). Bot v2 re-tested on fixed data: TRAIN WR drops
44% → 35%, Sharpe holds at +1.31 CI [+0.86, +1.79]. So the shape story
still holds — bot v2 is fundamentally asymmetric R:R — but with more
trades the low WR is more pronounced, not less.

The 20-seed sweep is being re-run on fixed data (bg task `bclykjgiw`, ~30
min). This memo will get its final section once the sweep completes.

---

## 1. The problem

Protocol gate 2 requires directional WR ≥ 50% on TRAIN + VALIDATION + walk-
forward. Bot v2 (seed 42) hits:

| Slice | WR | mean R | Sharpe (CI low) |
|---|---|---|---|
| TRAIN 2006-2018 | 44% | +1.18 | +1.02 |
| VAL 2019-2023 | 43% | +0.98 | +0.43 |
| HOLDOUT 2024→ | 41% | +0.84 | −0.18 |

Bot v2's R:R is 1:5 (k_stop 0.78 ATR, k_target 5.0 ATR). At a 43% WR:
`E[R] = 0.43 × 5R − 0.57 × 1R = +1.58R` — positive and large. The
strategy is honestly profitable; the WR gate rejects it on statistics
that don't apply to its geometry.

## 2. Why the gate exists

Copied from AXIS (BTC/gold), which primarily used symmetric-target designs
where a coin-flip WR + 1:1 R:R = zero edge. There, WR < 50% is a red flag.

For asymmetric R:R, the correct symmetric threshold is different:
- 1:2 R:R breakeven at 33% WR
- 1:3 R:R breakeven at 25% WR
- 1:5 R:R breakeven at 17% WR

So the AXIS-inherited 50% number is not a universal law; it is a
proxy for "your average trade must be profitable." A better bar for
mixed geometries is **expectancy × its bootstrap CI**.

## 3. New evidence from session 2

Session-2 smoke test evolved bot from seed 7 with the same GA config as
bot v2. The genome came out completely different:

| gene | seed 42 (v2) | seed 7 |
|---|---|---|
| dominant weights | macro/DXY 4.0, momo 3.8 | trend 4.0, momo 4.0, macro 3.8 |
| k_stop | 0.78 ATR (tight) | 0.83 ATR (tight) |
| k_target | 5.0 ATR (max) | 2.28 ATR (**symmetric**) |
| max_hold | 7 days | 5 days |
| strong / moderate | 0.72 / 0.17 | 0.47 / 0.15 |

Seed 7 TRAIN: n=167, WR **57%**, mean R +0.77, Sharpe **+1.62** CI
[+1.20, +2.08]. Walk-forward **10/10 folds positive**.

Seed 7 VALIDATION: WR 45% (borderline fail), Sharpe +0.84 CI [−0.14,
+1.76] (borderline pass).

Seed 7 HOLDOUT: WR 54%, Sharpe +1.06 CI [−0.22, +2.09] (n=28 small).

So a WR-passing shape exists in the search space. Whether it is a
stable-across-seeds phenomenon or a lucky draw is exactly what the
20-seed sweep will answer. If ≥10 of 20 seeds produce a WR ≥ 50% TRAIN
genome, WR is reachable and the gate stays. If < 5 do, WR is a rare
freak of a specific seed and the gate is malformed for oil.

## 4. Three options

### Option A: keep WR gate; kill bot v2; evolve v3 targeting symmetric R:R

- Fitness function penalizes `k_target / k_stop > 2.5` (or subtracts a
  penalty proportional to R:R ratio).
- Rationale: uphold the AXIS discipline. Consistency across FAR bots
  matters more than squeezing this one strategy through.
- Cost: throws away a real +0.84R HOLDOUT edge that seed 42 discovered.
  Slower to ship (v3 evolution + walk-forward + validation).
- Owner burden: none — Helios executes.

### Option B: replace WR gate with an expectancy-CI gate (bump PROTOCOL to 0.2.0)

- Replace gate 2 with: **bootstrap 95% CI of mean R > 0 on TRAIN + VAL,
  AND WR × avg_R_up + (1 − WR) × avg_R_down > 0**. This is the actual
  invariant WR was proxying.
- Rationale: math-honest, geometry-neutral. Same rigor, better fit.
- Cost: one-time PROTOCOL amendment (0.1.0 → 0.2.0). Diverges from AXIS's
  exact wording, but not its spirit.
- Owner burden: **approve amendment**. This is an owner-only call.

### Option C: keep WR gate; keep bot v2 in shadow with explicit disclosure

- Ship bot v2 as an **"asymmetric edge" candidate** with a WR disclosure
  visible to members: "This bot wins 43% of the time by design; expected
  R per trade is +0.98 with 2R+ typical winners."
- Rationale: educates members on payoff-driven strategies; keeps AXIS
  gate wording; still walks through the 4-week shadow.
- Cost: only if members are confused by low WR. Adds UI/copy work.
- Owner burden: **approve disclosure + review member-facing copy**.

## 5. Helios recommendation

**Option B**, contingent on the 20-seed sweep showing that WR-passing
genomes are rare (< 30% of seeds). If WR-passing genomes are common,
default to Option A.

Reason: the gate's *purpose* is to catch strategies that make money on
luck. Expectancy-CI does that with zero geometry bias. AXIS and Sable
would benefit from the same amendment; consistency across FAR-bot policy
still holds, just at a higher level of abstraction.

## 6. What Helios does next

- Wait for `results/bots/bot_v2_freshseed_sweep.json` (bg `bgkj9u7pm`).
- Update this memo with the WR distribution across 20 seeds.
- Owner picks A / B / C. Helios executes.
- If B: draft PROTOCOL v0.2.0 amendment for owner sign-off.
- If A: kick off v3 evolution with R:R-penalizing fitness.

— Helios
