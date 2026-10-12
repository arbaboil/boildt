---
name: Vega mirrored the schema-change notification convention + confirmed 2026-10-20 as autotrader-ship target
description: Vega's reply (2026-10-12) locks the symmetrical rule: our "Vega validator update required" commit header triggers a validator review before the next emission window.
type: project
---

**What Vega confirmed in the 2026-10-12 reply:**

1. **Schema-change convention mirrored.** Any Helios commit in
   `arbaboil/boildt` with header "Vega validator update required"
   triggers a validator review on the FAR side before the next
   emission landing. Vega watches for that header. Pure value changes
   within existing enums (e.g., the pending `HELIOS_COT_ENABLED` flip
   from always-0 to −1/0/+1) do not trigger review — the validator's
   `-1 | 0 | 1` range handles it.

2. **COT flip is zero-coordination.** When Owner flips the env flag,
   FactCell renders BULL/BEAR/IDLE for the cot component with
   appropriate color; `netVoteFromComponents` already handles 7
   components symmetrically; `available-votes` count derives from
   non-null count. No validator action required.

3. **Vega's reference to "2026-10-20 as the live-cutover date for
   Helios"** — Vega calls Helios "RIG" in that framing (the oil-side
   autotrader candidate shipping 10-20, parallel to Argus/BTC which
   is deferring autotrader indefinitely).

**Three distinct dates — Owner-confirmed through 2026-10-12 exchange:**
- **2026-10-20 — signals-only cutover for RIG.** Not autotrader. Per
  owner directive 2026-10-10 the autotrader is parked at option C
  (see `memory/project_helios_autotrader_parked_option_c_2026-10-10.md`).
  Signals already render live on /oil post Vega commit 9e76dc0
  (confirmed render: LONG @ $91.65).
- **~2026-11-04 — Gate 7 shadow-window formal completion.** 28
  weekday shadow files from the 2026-09-22 ship, net of the four
  lost in the 09-23 → 09-28 cron outage (not backfilled per
  data-honesty rule). Formal retirement of the PROTOCOL v0.2.1
  Gate 7 override. Signal model keeps emitting the whole way.
- **Post-2026-11-08 — autotrader review gate.** Oil autotrader
  re-opens for owner review only after this date and only if RIG
  clears its post-ship signals audit.

Owner directive 2026-10-12: do NOT relay a Gate-7-vs-10-20
correction to Vega. (Resolved by Vega's own 2026-10-12 reply —
Vega confirmed 10-20 is the signals-only ship, no correction
needed.)

**How to apply.** When Vega references "10-20 cutover" or similar, it
means the autotrader milestone, not Gate 7. Track both dates
independently. Continue the shadow window on autopilot toward
~2026-11-04; separately coordinate with Owner on autotrader-cutover
readiness as 10-20 approaches.
