---
name: feedback-verify-live-matches-validated-rule
description: Audit that the live emitter implements the exact validated trading rule (cadence, signal bar, entry, grading), and that a failing CI step can't skip the commit of safety flags.
metadata:
  type: feedback
---
The live pipeline ran for 7 weeks on a different rule from the validated one: daily re-price, not a Friday-close call. The grader also used look-ahead, and the drift control was inert because `exit 1` skipped the commit step.

**Why:** Owner's data-honesty rule. A published track record that doesn't match the backtest rule, or that grades with known prices, is a fake number even when every individual field is correct.
**How to apply:** At every ship/protocol change, diff the live emitter against src/sim/backtest.py (signal day, entry bar, stop logic, cool-off). Give every artifact-persisting step in CI `if: always()`. Check `gh run list` for red runs weekly, not just commits. Related: [[helios-weekly-protocol-fix-2026-11-10]]
