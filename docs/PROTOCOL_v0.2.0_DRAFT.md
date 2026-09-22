# HELIOS — Protocol Amendment v0.2.0 (DRAFT — awaiting Owner sign-off)

Status: **DRAFT — NOT YET IN FORCE**. Do not treat as authoritative.
Version: 0.2.0-draft-1
Author: Helios (2026-09-22)
Depends on: memo `docs/memos/2026-09-22_WR_gate_asymmetric_RR.md`
Trigger: 0/20 seeds in fresh-seed sweep achieve WR ≥ 50% on any slice;
all 20 converge to asymmetric R:R (4-7). Gate 2 as written filters out
oil's natural profitable-strategy family.

## What changes

### Gate 2 (Weekly engine + Bot) — REPLACED

**Old (v0.1.0):**

> Gate 2 — Directional WR (excl FLAT) ≥ 50%

**New (v0.2.0):** replaced by two components, both required.

> **Gate 2a — Expectancy CI.** Block-bootstrap 95% CI lower bound of
> `mean_r_net` > 0 on TRAIN AND VALIDATION.
>
> **Gate 2b — Payoff-adjusted WR invariant.** Let `avg_R_up` = mean net R
> across winning trades, `avg_R_down` = |mean net R across losing trades|
> (positive number). Require:
>
>     WR × avg_R_up  -  (1 − WR) × avg_R_down  ≥  +0.05  (in R)
>
> Rationale: this is the invariant that WR ≥ 50% was proxying for a
> symmetric-R:R strategy. It reduces exactly to `WR ≥ 50%` when
> avg_R_up = avg_R_down = 1R. For asymmetric geometries, it enforces
> the true condition — average trade must be profitable — with a small
> positive margin (0.05R ≈ half a cost roundtrip) to prevent shipping
> break-even strategies.

Gates 1, 3, 4, 5, 6, 7 unchanged.

### Effect on candidates

Rule: `strict_v020_pass = g1 ∧ g2a ∧ g2b ∧ g3 ∧ g4 ∧ g5 ∧ g6 (on TRAIN
+ VALIDATION + walk-forward)`.

Then Gate 7 (silent-live shadow, ≥ 4 weeks) begins as usual.

Compatibility: v0.2.0 is STRICTER than v0.1.0 in the corner where a
strategy is 50% WR with zero expectancy (e.g., 50% × 1R − 50% × 1R = 0R
+ small edge lost to costs). v0.1.0 would pass such a strategy; v0.2.0
rejects it. This is intentional — v0.1.0 was permissive in that corner
by accident.

## Bot ship gates

No change. B1-B6 already reference net edge and expectancy directly, so
they were geometry-neutral. B7 (fresh-seed retest) still requires median
of the sweep's per-seed reports to pass gates 1-6. Under v0.2.0, gate 2
is 2a + 2b; a median-passing seed must clear both.

## Data-honesty rules

Unchanged. The FLAT-rate + directional-WR reporting continues verbatim.
The v0.1.0 rule "FLAT calls never count as wins" is preserved — we still
report WR over directional trades only, we just no longer use it as a
gate.

## Rationale (short)

- **20-seed sweep evidence** (2026-09-22): 0/20 seeds pass WR ≥ 50% on
  TRAIN or VAL. All 20 converge to R:R 3.9-6.7. The gate is not
  reaching a strategy that doesn't exist in the oil signal space.
- **Bot v3 seed 7** passes all other gates on all three slices including
  Gate 6 permutation (p = 0.000 / 0.003 / 0.008). Under v0.2.0, seed 7
  would proceed to Gate 7 shadow. Under v0.1.0, it is blocked.
- The v0.1.0 gate was inherited from AXIS (BTC/gold), where symmetric-R:R
  strategies dominate the profitable set. Oil is different. Copying the
  AXIS number for oil turns out to be a geometry mismatch.

## Rejected alternatives

- **Option A — keep v0.1.0, add WR-penalty fitness for v3.** Ruled out
  by the sweep: no genome in the search space achieves WR ≥ 50% while
  keeping edge.
- **Option C — ship v2 with WR disclosure.** Superseded by seed 7 which
  is materially better than v2; also, disclosure doesn't fix a
  policy-level bar. Members would still see a "bot violates our own
  gate" note, which erodes trust.

## What Helios does on sign-off

1. Bump `docs/PROTOCOL.md` version 0.1.0 → 0.2.0. Rename Gate 2 to
   Gate 2a + 2b, replace threshold text. Append amendment log entry.
2. Re-run `scripts/candidate_audit.py` on seed 7 to confirm v0.2.0 pass.
   (Fast, deterministic; already tested at draft-time — passes.)
3. Start `--candidate bot_v3_seed7_candidate.json` Gate 7 shadow window.
   Duration ≥ 4 weeks; success = shadow WR + expectancy inside walk-
   forward fold envelope. On drift → pause, root-cause.
4. Announce internal-only: candidate 1 for the oil bot line.

## Signature

    OWNER  ______________________  DATE _______________

    Reject / Approve / Approve with edits (strike-through):

    ______________________________________________________________

    ______________________________________________________________
