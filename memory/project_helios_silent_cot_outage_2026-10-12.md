---
name: Silent COT WTI data outage 2022-02 → 2026-10 (fixed 2026-10-12)
description: CFTC rename of WTI NYMEX contract name silently blanked cot_mm_net_wti for 4+ years; live model's vote_cot=0 on all shadow calls until the fix
type: project
---

**What happened.** CFTC renamed WTI NYMEX contract from
`CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE` to
`WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE` on 2022-02-01. The puller
in `src/data/cot.py` queried the SODA `72hh-3qpy` dataset by
`market_and_exchange_names`, so it silently returned zero rows post-rename.
`cot_mm_net_wti` has been NaN for all of HOLDOUT (2024→present) and the
first 10 days of the Gate-7 shadow window. All 10 shadow entries show
`votes.cot = 0`.

**Fix (commit TBD).** Query by `cftc_contract_market_code = '067651'`,
which is stable across the rename. WTI COT restored to 1061 rows through
2026-10-06. Brent (code `06765T`) was unaffected.

**Why it stayed silent.** The puller's downstream feature-build pipeline
treats missing COT values as `NaN`, which `regime_vote.score_matrix` maps
to `vote_cot = 0` (abstention). The candidate audit metrics stayed
consistent across the gap because `vote_cot = 0` is a valid state. Only
feature-coverage inspection (non-null % by year) exposed the outage.

**Impact.** Re-audited seed 7 with corrected data — all v0.2.0 gates
still pass:
- TRAIN 234 / mean R +1.29 (unchanged)
- VAL   97 / mean R +0.98 (was 95 / +0.92)
- HOLDOUT 58 / mean R +0.73 (was 54 / +0.73)

Live behavior change on next cron run: cot vote begins firing per
genome (w_cot=0.98, cot_bull=-0.64, cot_bear=+2.5 — contrarian).
Expected ~1-2 extra signals per quarter. Fix was committed; owner needs
to approve deploy to live cron on next push.

**Why:** Four-year silent data gap on a live-feature pipeline. Shows how
free public-dataset renames can cripple a model without any error
signal. Future pullers should **query by stable code**, not name, when
the data source supports it.

**How to apply.** When adding new free-data pullers:
1. Prefer stable codes/IDs over human-readable names.
2. Add a data-freshness assertion to the puller — e.g., fail loudly if
   the latest row is more than N weeks behind today.
3. Add a feature-coverage test to `tests/` that fails if any required
   feature column drops below 80% non-null on the HOLDOUT slice.

**Validate fix:** Rerun `python scripts/pull_data.py` then
`python -c "import pandas as pd; f=pd.read_parquet('data/processed/features.parquet'); print(f[f.date.dt.year>=2024]['cot_mm_net_wti'].notna().mean())"` — should be ~1.0.
