# HELIOS — Handoff pack for FAR site integration

Audience: Vega (or whoever wires HELIOS into `C:\dev\FarACtionRadar\v16build\web\`)
Owner: Helios agent + FAR Owner
Version: 0.1.0-draft (locks with first ship)

## What HELIOS produces

Three artifact families under `results/emitted/`:

```
results/emitted/
  weekly/current.json        # weekly regime call
  daily/current.json         # daily brief (shadow_only=true by default)
  backtest/summary.json      # frozen per-candidate audit stats
```

Schemas: `docs/DATA-CONTRACT.md`. All are contract-compliant, versioned
(`schema_version: 1`), and safe for public-read.

## What HELIOS does NOT do

- Does not push to R2. Site side owns the R2 upload (via a scheduled
  Worker or GH Action pulling from `results/emitted/`).
- Does not render UI. Site owns the "HELIOS calibrating" / "Live signal"
  render logic based on `shadow_mode` and `direction`.
- Does not persist history. `history/index.json` and per-week files are
  built by the site loader on emit-then-append. HELIOS provides the raw
  current-call payload each cadence.

## Integration steps

1. **Provision R2 buckets**: `helios-data-staging`, `helios-data-prod`.
   Public-read. CORS: allow the FAR site origins.

2. **Add HELIOS to the site's build pipeline**. Two options:
   - **Option A — Vega-hosted Worker.** New worker at
     `web/helios-engine/` mirroring `web/axis-engine/`. On schedule
     (weekly Fri 21:15 UTC + daily 17:00 UTC weekdays), fetch latest
     HELIOS output artifacts from R2 or Git, upload to `helios-data-{env}`,
     bump `history/index.json`.
   - **Option B — GH Action.** Cron job in `.github/workflows/helios-emit.yml`
     runs the HELIOS script (`python scripts/emit_reads.py`), uploads
     to R2 via wrangler, commits history back.

   Recommended: Option B for phase-1 (simpler, no Worker infra to
   maintain). Migrate to Option A once daily brief also ships.

3. **Add loader on the site**. Mirror the AXIS loader pattern in
   `web/src/lib/axis/`. New folder `web/src/lib/helios/` with
   `types.ts` (from `docs/DATA-CONTRACT.md`), `loader.ts`
   (`fetch` + `zod` validate + 30s stale-while-revalidate), and
   `render.tsx` (banner + read + component-vote breakdown).

4. **Wire the site tab**. Add "Oil (HELIOS)" tab to the members
   dashboard. Under `shadow_mode: true` render "HELIOS calibrating —
   signals go live after N more weeks" with a link to `docs/PROTOCOL.md`
   for what's being audited.

5. **Kill-switch**: see `docs/DEPLOY-PLAN.md`. Site must check
   `provenance.kill_switch_engaged` before rendering signals.

## Test plan (for Vega)

- **Schema round-trip**: fetch each artifact, `zod.parse` against the
  types generated from DATA-CONTRACT. Reject unknown keys? No — allow
  unknown for forwards-compatibility (schema_version bumps let us
  add fields).
- **Shadow render**: verify `direction: "SHADOW"` and `shadow_mode: true`
  produce the calibration banner, not a signal.
- **Kill-switch**: manually set `provenance.kill_switch_engaged: true`
  in a staging artifact; confirm site suppresses.
- **Zero-signal render**: `direction: "FLAT"` should show a "stand down
  this week" card, not a blank.
- **Stale detection**: if `published_utc` is > 8 days old for weekly or
  > 2 days for daily, render "HELIOS data stale" banner. This is the
  first line of defense against a broken cron.

## What HELIOS still needs from Owner

1. **PROTOCOL v0.2.0 sign-off** (`docs/PROTOCOL_v0.2.0_DRAFT.md`).
   Without this, HELIOS ships in shadow-only forever — bot v3 seed 7
   is blocked by WR gate as PROTOCOL v0.1.0 stands.
2. **EIA API key** for the weekly petroleum status feed. Currently the
   `eia_stocks_surprise` feature is a naive weekly-diff proxy; a real
   surprise (vs consensus proxy) would materially strengthen signals
   in the day-after-EIA windows.
3. **R2 credentials + bucket provisioning** — same pattern as AXIS
   (`AXIS_DATA_STAGING` / `AXIS_DATA_PROD`). New env vars:
   `HELIOS_DATA_STAGING`, `HELIOS_DATA_PROD`, `HELIOS_R2_TARGET`,
   `HELIOS_SHADOW_MODE`.
4. **Approval to hand this pack to Vega**. Helios does not talk to Vega
   directly.

## Files in this handoff

Everything below is safe to hand over verbatim:

```
docs/
  MISSION.md
  ARCHITECTURE.md
  PROTOCOL.md
  PROTOCOL_v0.2.0_DRAFT.md
  DATA-CONTRACT.md          # site integration target
  HANDOFF.md                # this file
  DEPLOY-PLAN.md            # kill-switch + monitoring spec
  LAB-NOTEBOOK.md           # provenance
  REALISM.md                # fidelity score
  DATA-SOURCES.md
  RESEARCH-PLAN.md
  memos/2026-09-22_WR_gate_asymmetric_RR.md

src/                          # engine source (read-only for Vega)
scripts/emit_reads.py         # HELIOS's contract emitter — Vega calls this
results/bots/bot_v3_seed7_candidate.json          # the candidate
results/bots/bot_v3_seed7_candidate_audit.json    # full gate audit
results/monte_carlo/bot_v3_seed7_candidate_mc.json # forward-path CIs
results/emitted/                                  # sample outputs
```
