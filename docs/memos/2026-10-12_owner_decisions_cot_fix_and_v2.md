# Owner message — 2026-10-12 session

Three decisions queued. Full context in referenced docs; TL;DR here.

## 1. Silent COT WTI data bug — fixed, needs deploy approval

**Bug.** CFTC renamed WTI NYMEX contract (`CRUDE OIL, LIGHT SWEET` →
`WTI-PHYSICAL`) on 2022-02-01. Puller was looking up by market name,
silently returned zero rows after rename. `cot_mm_net_wti` has been
NaN for the entire HOLDOUT (2024→present) and the 10-day shadow strip.
Live model's `vote_cot = 0` on every call since go-live.

**Fix.** Query SODA by `cftc_contract_market_code` (stable across
rename). Verified: WTI COT now 1061 rows through 2026-10-06.

**Impact.** Re-audited seed 7 with corrected data. HOLDOUT: 54 → 58
trades (+4), mean R unchanged at +0.73. All gates still pass. Live
behavior change on next cron: cot vote begins firing per genome
(contrarian, w_cot=0.98) → ~1-2 extra signals per quarter.

**Deploy options.**
  - (a) Let the fix roll. Drift monitor is the safety net. Recommended.
  - (b) Pin a `cot_disabled` flag until formal v0.2.2 lock. **Landed in
    commit 6f99844** — `HELIOS_COT_ENABLED` env var, pinned to `false`
    on the daily cron. Flip to `"true"` in `.github/workflows/daily.yml`
    to execute option (a).
  - (c) Pause live, re-audit holistically, re-enable.

Current state: option (b) is live. The daily cron continues to emit
with `vote_cot=0` (preserving pre-fix behavior) until Owner edits the
workflow to flip the env var. Monte Carlo + ship_readiness have been
refreshed on honest data (commit 10cfd49) so you can see what the
future looks like once the flag flips.

Full details: `docs/V2-FEATURE-RESEARCH.md` §Finding 0.

## 2. Daily cadence v0.3.0 approach

**Blocker.** Daily cadence of seed 7 fails Gate 5 only on TRAIN
(max_dd 18.4R vs 15R gate). VAL + HOLDOUT already pass. Root cause:
2013 chop regime, not a crisis. Daily fires 2.8× more trades than
weekly, accumulating losses during chop.

**Recommended path.** Stack chop-regime filter (option A) + 3-day
post-stop cool-off (option B). Expected to cut TRAIN DD below 12R
while preserving VAL+HOLDOUT edge. No new genome evolution required
unless A+B don't clear.

**Not recommended.** Position sizing (option D) — breaks R-geometry
and complicates artifact schemas Vega integrates with.

Full details: `docs/DAILY-V03-SCOPE.md`.

## 3. v2 feature research scope (Phase 2a)

**Recommended Phase 2a (next 2 weeks post-ship):**
- COT depth features: delta_4w, percentile_156w, long/short ratio,
  positioning-vs-price divergence.
- EIA expansion: distillate/gasoline surprises, crack margin,
  refutil delta.

Both are drop-in — expand existing pulls, re-sweep GA.

**Backlog.** OPEC compliance (PDF scrape), GDELT geopolitics,
hurricane risk, Baker Hughes. In priority order.

Full details: `docs/V2-FEATURE-RESEARCH.md`.

## Session scorecard

Also landed this session (no owner input needed):
- Pinned `ubuntu-24.04` on both workflows to survive the 2026-10-19
  `ubuntu-latest` → Ubuntu 26 migration during Gate 7 window.
- `ship_readiness.py` now reflects PROTOCOL v0.2.1 — reports
  `live_status`, kill-switch state, drift monitor state, and keeps
  v0.2.0 "would-pass-without-override" as a separate signal.
- `scripts/shadow_strip_audit.py` — reconstructs realized R per
  emitted weekly call. 2 closed trades = -2R vs model expectation
  of +0.92R/trade on VAL. Within normal probability for a 31% WR
  strategy (p ≈ 0.47 of two consecutive stops) but worth tracking.
- `HELIOS_COT_ENABLED` env flag gates the COT fix behind an explicit
  owner-approval step on the daily cron (default enabled for research,
  pinned false for live). Owner flips the workflow value to deploy.
- `tests/test_feature_coverage.py` — new 10-column coverage gate on
  HOLDOUT, floors each feature at 80% non-null. Would have caught
  the silent COT outage in Feb 2022.
- Monte Carlo refreshed on corrected COT data: P(final>0, 1yr) =
  99.2%, P(ruin) = 0%, mean +1.125 R/trade. Marginally better than
  pre-fix.
- 103 → 114 tests pass.

Draft responses to each decision point and I'll execute.
