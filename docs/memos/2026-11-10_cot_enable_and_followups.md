# 2026-11-10 — COT vote enabled + follow-up decisions

Owner delegated these to Helios ("continue with the most logical decision").

## 1. COT vote: ENABLED (option (a) from the 2026-10-12 memo)

`HELIOS_COT_ENABLED: "true"` in `.github/workflows/daily.yml`, effective on
the next cron run.

**Why now:** the live-tracked record starts with W47 (week of 2026-11-16).
If the COT fix is ever going live, the only time it doesn't split the record
across two models is before W47. The data fix itself is a correctness fix
(CFTC renamed the WTI contract in Feb 2022, and the puller silently returned
NaN). It is not a new feature chosen by looking at results; option (a) was
already the recommendation on 2026-10-12.

**Re-audit on 2026-11-10 data** (`scripts/candidate_audit.py`, same genome):

| Slice | COT off: n / WR / mean R / Sharpe CI low / DD | COT on |
|---|---|---|
| TRAIN | 233 / 41% / +1.39 / +1.39 / 8.1R | 234 / 39% / +1.29 / +1.32 / 8.1R |
| VAL | 97 / 34% / +0.86 / +0.45 / 14.1R | 97 / 36% / +0.98 / +0.66 / 8.7R |
| HOLDOUT | 57 / 32% / +0.74 / +0.21 / 8.8R | 59 / 34% / +0.79 / +0.37 / 6.8R |

All PROTOCOL v0.2.0 gates pass on every slice. B6 regime consistency passes.
Walk-forward: 10/10 folds positive. `results/bots/bot_v3_seed7_candidate_audit.json`
was replaced with the COT-on audit (the old one dated from 2026-09-22, built on
COT-blank data), so the site's `backtest/summary.json` now matches the live
model. The genome and `genome_hash` are unchanged.

**Effect on the 11-09 SHORT:** none. That call is frozen.

## 2. Autotrader review gate: tied to live-tracked sample size

The 11-08 review gate assumed a clean post-ship record. There isn't one yet:
every week before W47 is "pre-fix protocol". New gate:

- **Earliest review:** once **12 live-tracked weekly calls have resolved**
  (W47 onward, FLAT excluded from the count, reported separately). That's
  roughly mid-February 2027.
- **Pass condition for opening the review** (not for shipping):
  realized mean R per directional call within the VAL bootstrap 95% CI;
  no kill-switch or drift incidents left unexplained; publish-time SLA met
  (every call before Mon 00:00 UTC).
- **Why 12:** at a ~35% WR, 12 calls is the smallest sample where "all
  stops" (p ≈ 0.6%) cleanly separates from the model's expected distribution.
  Fewer is noise.

## 3. Market-holiday stale-guard false-fails: FIXED

`src/util/session.py` now has a NYMEX holiday calendar (New Year, MLK,
Presidents, Good Friday, Memorial, Juneteenth, July 4, Labor, Thanksgiving,
Christmas; Columbus and Veterans Day trade). On a holiday, `shadow_log` asks
for the prior session instead of failing. First live case: Thanksgiving,
2026-11-26.

## 4. Ubuntu 24.04 pin: KEPT

No environment changes while a new track record builds. Revisit at the
autotrader review gate, or sooner if GitHub announces 24.04 deprecation.

## 5. Daily brief: stays shadow-only

Unchanged. Its Gate 5 (TRAIN max-DD) still fails. The v0.3.0 scope in
`docs/DAILY-V03-SCOPE.md` remains the path.
