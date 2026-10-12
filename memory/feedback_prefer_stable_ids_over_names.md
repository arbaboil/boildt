---
name: Prefer stable IDs over human-readable names when pulling free data
description: Public datasets rename contracts/series mid-stream; names break silently, codes survive. Add freshness assertions to catch silent-NaN futures.
type: feedback
---

**Rule.** When pulling from a free public data source, query by the most
stable identifier the source exposes (contract code, FRED series ID,
EIA series key) — never by the human-readable name alone. Names get
renamed; downstream pulls silently return zero rows; downstream features
go NaN; downstream model votes abstain; downstream backtests still pass
gates — the outage is invisible.

**Why:** On 2026-10-12 found the CFTC WTI COT puller had returned zero
rows for 4+ years because `CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE
EXCHANGE` was renamed to `WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE`
on 2022-02-01 while the stable `cftc_contract_market_code=067651`
survived. All live shadow entries had `vote_cot = 0` because of this.
See `memory/project_helios_silent_cot_outage_2026-10-12.md`.

**How to apply:** Every new puller under `src/data/` should:
1. Query by stable code/key when the API offers one.
2. Fail loudly (raise, don't silently return empty) if the latest row
   is more than N weeks behind `today - vintage_lag`. Pick N per
   source's publication cadence (COT weekly → N=3; EIA weekly → N=3;
   OPEC monthly → N=6 weeks).
3. Ship with a `tests/test_<source>_freshness.py` that fails CI on
   stale pulls when run locally against the live endpoint. Mark as
   `@pytest.mark.network` so it only runs under a dedicated job.
4. Ship with a `tests/test_feature_coverage.py` fixture that fails if
   any required feature column drops below 80% non-null on the HOLDOUT
   slice after `scripts/build_features.py`.
