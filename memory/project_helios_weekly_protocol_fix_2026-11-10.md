---
name: helios-weekly-protocol-fix-2026-11-10
description: Live weekly call was re-priced daily + graded with look-ahead + drift flag never persisted; fixed 32ad319/24500dd. RIG live-tracked from W47 (2026-11-16); earlier weeks = "pre-fix protocol, regraded".
metadata:
  type: project
---
Found 2026-11-10 while answering Vega's relay (publish timing, live status, R2).

- Weekly call is now: Friday-close read (completed-bar rule, 22:00 UTC) -> week_of next Monday -> frozen on first publish. Publish slots: Fri 22:30 UTC run, backstops SAT 12:00 / SUN 12:00 / SUN 19:00 UTC.
- Grader = backtest-identical (entry = first close after signal bar). Regraded record: 7 resolved, +11.08%, WR 2/7 (old site said +13.94% on 6).
- Owner decisions 2026-11-10: push + keep archives (regrade only); RIG "live" from W47; weeks before 11-16 labeled pre-fix.
- Open Owner items: drift confidence-outlier check miscalibrated (sigma 2.6 around 92) and will now actually force SHADOW on trip; R2 prod token scope untested (first prod upload = 2026-11-10 22:30 UTC cron). The repo token can't dispatch workflows (403 admin).
- Full details: docs/memos/2026-11-10_weekly_protocol_fix_and_regrade.md

**Why:** Vega/social treat every LONG/SHORT as a tracked call and the on-chain Forecast Registry records the call at publish time from W47 on.
**How to apply:** Never let a published weekly be recomputed. Any change to the call or grading semantics needs a regrade memo + a Vega note. Related: [[feedback-verify-live-matches-validated-rule]]

**Vega ack 2026-11-10:** /oil dims pre-W47 weeks with the tag "pre-fix protocol, regraded". WR counts live-tracked weeks only. Beta note says live from 2026-11-16. GitHub stays the fallback (the site uses whichever of R2/GitHub is newer). Friday-close + publish-by-Saturday + freeze-on-publish confirmed compatible with the Forecast Registry. Next step: check the 2026-11-10 22:30 UTC cron's R2 prod upload. If it fails on token scope, tell Vega and Farhad issues a prod token.
