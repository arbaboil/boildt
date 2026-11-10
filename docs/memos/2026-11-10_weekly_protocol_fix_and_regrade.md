# 2026-11-10 — Weekly publish protocol fix + track-record regrade

**Status:** Owner-approved 2026-11-10 (push now, keep archives, live from W47).
**Commits:** 32ad319 (code), this commit (regraded index + memo).

## What was wrong (found answering Vega's 2026-11-10 relay)

1. **The weekly call was not a single weekly call.** `emit_reads` built the
   weekly payload from *whatever the latest bar was* on every weekday run, and
   `emit_history` overwrote `history/{week_of}-weekly.json` each time. Entry,
   stop and target were re-priced up to 5×/week. The archived "call" was the
   last re-price of the week. Direction never flipped mid-week in the 8 live
   weeks (checked via git history), but levels did.
2. **This did not match the validated rule.** The seed-7 genome is weekly
   cadence (`daily_cadence=False`, `entry_gate_day=4`): read on the **Friday
   close**, enter at the next close.
3. **In-progress bars.** Crons slipped from 21:00 to 00:00–03:00 UTC. By then
   Yahoo serves the *next* session's in-progress bar, which fed the call (e.g.
   the 11-09 SHORT was computed at 03:06 UTC Tue off a partial Tue bar).
4. **Look-ahead in grading.** The grader walked closes from Monday (`week_of`)
   while the call was priced later in the week, so closes known at publish
   time could trigger the stop/target.
5. **Drift control silently inert.** `drift_monitor.py` tripped on 10-30,
   11-03, 11-05 and 11-06 (confidence outlier), but the workflow aborted before
   the commit step, so `admin/drift.flag` never persisted and never forced
   SHADOW. Those runs also published nothing, which is why calls landed late.
6. **Stale guard false-fails.** A Fri 21:00 run that slipped past midnight UTC
   requested Saturday's bar and failed (10-31, 11-07).
7. **R2 prod never written.** The workflow only uploaded to `helios-data-staging`.

## What changed

| Area | Now |
|---|---|
| Signal bar | Last completed bar ≤ Friday (Thu if Friday is a holiday). Completed = `now ≥ bar date + 22:00 UTC`. |
| Week | Friday signal → `week_of` = the following Monday. |
| Freeze | The first publish for a `week_of` is archived and re-served verbatim. Never re-priced. |
| Publish time | Earliest: Fri 22:30 UTC run. Backstops Sat 12:00, Sun 12:00, Sun 19:00 UTC (day-name crons). Target: well before Mon 00:00 UTC. |
| Grading | Same as `src/sim/backtest.py`: entry = first close after the signal bar; stop/target = entry ∓ k·ATR20; close-based; stop wins ties; resolves on first hit, else `max_hold` after 11 rows. Gross of costs. |
| Drift | Checked **before** the weekly is archived; re-emit after the check so a trip publishes SHADOW. Commit + R2 run `always()`. |
| R2 | Uploads to `helios-data-prod` and `helios-data-staging`. |

## Regrade (archives unchanged; only the grader changed)

| Week | Dir | Old site | Regraded |
|---|---|---|---|
| 09-21 | LONG | stop −1.73 | stop −1.73 |
| 09-28 | LONG | max_hold +4.54 | max_hold +12.23 |
| 10-05 | LONG | target +17.56 | max_hold +8.82 |
| 10-12 | LONG | stop −2.25 | stop −2.02 |
| 10-19 | LONG | stop −2.46 | stop −2.42 |
| 10-26 | LONG | stop −1.72 | stop −1.64 |
| 11-02 | LONG | (open) | stop −2.16 |
| 11-09 | SHORT | open | open |

Regraded, 7 resolved: **sum +11.08%**, directional WR **2/7 (29%)**, FLAT 0/7.
This fits the model's asymmetric profile (validation WR 33–36%, R:R ≈ 6).
Old site figures (6 resolved): +13.94%.

**Status of these weeks:** "pre-fix protocol, regraded". RIG counts as
live-tracked from **W47 (week of 2026-11-16)**, the first call made under the
validated Friday-close rule and the first one recorded in the Forecast Registry.

## Open items for Owner

- **Drift confidence-outlier check is miscalibrated.** The 14-day baseline is
  nearly constant (median 92, σ 2.6), so any FLAT-leaning or lower-confidence
  read trips it (z 8.8–26.9). Now that the flag actually persists, a trip at
  Friday publish will make that week's call SHADOW. Proposed: floor σ at 10
  confidence points, or switch to a direction/coverage-only check. This is an
  Owner decision because it loosens a compensating control.
- **R2 prod token scope.** If the current R2 secret can't write
  `helios-data-prod`, the upload step warns and the run goes red. Owner then
  issues a prod-scoped token.
