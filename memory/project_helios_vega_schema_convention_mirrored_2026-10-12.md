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

**Vega's framing of 10-20 may not line up with Gate 7 math.** 10-20
was the pre-cron-outage Gate 7 completion date. Post-outage
(4 silent-no-op commits 09-23 → 09-28, see
`memory/project_helios_cron_outage_2026-09-29.md`), Gate 7 completes
~2026-11-04 Wednesday (18 shadow days remaining as of 2026-10-09
cron per `results/ship_readiness.json`). Three possibilities:
  (a) Vega missed the outage memo and is tracking the pre-outage date.
  (b) Owner is planning a second early-ship override (like v0.2.1)
      for the autotrader cutover on 10-20 with Gate 7 completion
      following behind.
  (c) The "live-cutover" term refers to something other than Gate 7
      completion (e.g., engine-signal visibility already live post
      Vega's 9e76dc0 fix, with autotrader cutover gated separately).
Needs Owner clarification before any coordination with Vega or
scope planning around a 10-20 ship.

**How to apply.** Treat 10-20 as a *soft* target subject to Owner
clarification. Do not plan autotrader ship work around 10-20 until
Owner confirms Gate 7 handling. Continue shadow window on schedule
toward ~2026-11-04 as the formal Gate 7 completion.
