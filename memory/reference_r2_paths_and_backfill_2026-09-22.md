---
name: R2 bucket path convention + recent-calls backfill policy (locked 2026-09-22)
description: Vega confirmed all HELIOS artifacts live at BARE paths inside helios-data-staging / helios-data-prod. No argus-signals/helios/ prefix. Recent-calls strip is sparse-but-honest (no backfill).
type: reference
---

**R2 key path convention (locked).** All artifacts land at bare paths inside the HELIOS bucket. NO prefix. Full list:

```
helios-data-staging/weekly/current.json
helios-data-staging/daily/current.json
helios-data-staging/backtest/summary.json
helios-data-staging/backtest/curve.json
helios-data-staging/history/index.json
helios-data-staging/history/{YYYY-MM-DD}-weekly.json
helios-data-staging/admin/killswitch.json
```

Same paths in `helios-data-prod`. Vega's loader `lib/helios/data.ts` reads via `${RAW_BASE}/{key}` with `RAW_BASE` being the bucket dev URL (per `docs/DEPLOY-PLAN.md` §R2 target). If Vega ever mentions "argus-signals/helios/..." in messages, that's documentation shorthand from Argus's separately-named bucket — not a path change. Do not add a prefix.

**Recent-calls strip policy (locked).** Sparse-but-honest. NO backfill of past weeks from HOLDOUT walk-forward simulation. Reasons (Vega's):

1. Double-count vs the backtest reference strip (WR/Sharpe/DD already reflect those trades).
2. Dilutes the "Live-tracked, unedited" tagline.
3. Mixed cadences (simulated vs live) read as spin even with backfill=true labels.

AXIS + NORTH shipped with sparse strips. The `DAY X of 28 · CALIBRATING` badge already signals "brand new". First real live entry is 2026-09-21; first resolved entry ~2026-10-02 (11-day max_hold elapses).

**How to apply.** If a future session considers adding backfill or changing the path structure, re-read Vega's rationale first. Only change if Vega explicitly asks — this is Vega territory.
