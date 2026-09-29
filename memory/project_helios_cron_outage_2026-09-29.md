---
name: Helios cron shadow-log outage 2026-09-22 → 2026-09-29
description: Silent commit no-op on cron since SHIP LIVE; two bugs (git add abort on missing path + weekend staleness) fixed 2026-09-29
type: project
---

Between 2026-09-22 (SHIP LIVE commit `b88ad80`) and 2026-09-29, the daily-shadow-log cron ran 7 times: 4 successes (09-23, 09-24, 09-25, 09-28) that silently committed nothing, and 2 hard failures (09-26 Sat, 09-27 Sun). Only 2 of the 7 expected shadow files landed on `origin/main`. Fixed in commit `7a54f9c` (2026-09-29).

**Bug 1 — `git add` aborts and stages nothing on missing pathspec.**
The commit step ran `git add results/emitted/ results/shadow/ results/ship_readiness.json results/drift_status.json admin/drift.flag 2>/dev/null || true`. `admin/drift.flag` only exists when drift is detected — never has been. Git 2.55 behavior: when any pathspec doesn't match, it exits fatal AND does not stage the valid paths that preceded it. `|| true` swallows the exit code but doesn't recover the staging. So every weekday cron ran the pipeline correctly, uploaded to R2 (so the FAR site stayed current), then silently skipped commit. Fix: split into separate `git add` calls, guard optionals with `[ -f ... ]`.

**Bug 2 — weekend runs fail on stale-data guard.**
No fresh WTI close arrives Sat/Sun. `shadow_log.py` refuses to write when `effective_asof < requested_asof` (correct behavior — protects against silent stale reads). Weekend cron therefore always errored with exit 3. Fix: cron schedule to weekdays only (`0 21 * * 1-5`). Fri 21:00 UTC catches the Fri 5pm ET (EDT) close.

**Why:** Not backfilling the 4 missing weekday shadow logs (09-23, 09-24, 09-25, 09-28) even though the data is fully reproducible from FRED. Data-honesty rule — silent-live evidence must be genuine, not reconstructed. The outage is transparent in the git log.

**How to apply:** From 2026-09-29 forward, `results/shadow/*.json` on `origin/main` is the authoritative Gate 7 evidence stream. Ship-readiness will show inflated "days remaining" until the real 28-day window completes (~2026-11-08 given the gap). R2 stayed fresh throughout the outage, so live site behavior was unaffected — this bug was auditability-only. When designing future cron commit steps: separate git add per optional artifact, or use `git add -A <dir>` on trusted dirs.

**Validate fix:** Next scheduled run 2026-09-29 21:00 UTC. Expected: commit lands on main with `results/shadow/20260929.json`, `results/drift_status.json`, refreshed emitted/*. Look for `--- staged changes ---` block in the run log (added for debuggability).
