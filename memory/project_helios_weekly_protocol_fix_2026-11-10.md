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
- Drift confidence-outlier sigma floored at 10 pts (Owner 2026-11-10); a trip needs |delta| > 20.
- Open: R2 prod token scope untested (first prod upload = 2026-11-10 22:30 UTC cron). The repo token can't dispatch workflows (403 admin).
- Full details: docs/memos/2026-11-10_weekly_protocol_fix_and_regrade.md

**Why:** Vega/social treat every LONG/SHORT as a tracked call and the on-chain Forecast Registry records the call at publish time from W47 on.
**How to apply:** Never let a published weekly be recomputed. Any change to the call or grading semantics needs a regrade memo + a Vega note. Related: [[feedback-verify-live-matches-validated-rule]]

**Vega ack 2026-11-10:** /oil dims pre-W47 weeks with the tag "pre-fix protocol, regraded". WR counts live-tracked weeks only. Beta note says live from 2026-11-16. GitHub stays the fallback (the site uses whichever of R2/GitHub is newer). Friday-close + publish-by-Saturday + freeze-on-publish confirmed compatible with the Forecast Registry. Next step: check the 2026-11-10 22:30 UTC cron's R2 prod upload. If it fails on token scope, tell Vega and Farhad issues a prod token.

**Delegated decisions 2026-11-10 (Owner: "most logical decision"):** COT vote ENABLED before W47 so the whole live record runs on one model (re-audit: all gates pass, HOLDOUT CI low +0.21 to +0.37, WF 10/10; audit JSON replaced). Autotrader review earliest after 12 resolved live calls from W47 (~mid-Feb 2027). NYMEX holiday calendar added to the stale guard. Ubuntu 24.04 pin kept. Details: docs/memos/2026-11-10_cot_enable_and_followups.md

**Session wrap 2026-11-10:** generated_at_utc shipped (cb37995). Vega serves the newer of R2/GitHub; with no timestamp on either copy, GitHub wins. Pending checks: the 11-10 22:30 UTC R2 prod upload, and the W47 publish on Sat 11-14.

**R2 prod update 2026-11-11:** The first prod upload (11-11 02:02 UTC) got AccessDenied on every file, and the step stayed green (errexit bug, fixed b3aee04, see [[feedback-bash-errexit-subshell-or]]). The Owner widened the existing token "HELIOS daily cron uploader" to R/W on both buckets (same key). Prod writes are still UNCONFIRMED at wrap. Next action: read the READBACK lines from the first run after b3aee04 and send Vega the upload time + generated_at_utc per file. Vega flips NEXT_PUBLIC_HELIOS_TARGET to prod only after that. Note: GitHub has been starting the 22:30 cron 2-4 h late, and a late start can trip the stale guard.
