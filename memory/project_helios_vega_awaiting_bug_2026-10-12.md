---
name: Vega-side AWAITING bug fix 2026-10-12 (site now renders tri-state votes)
description: FAR site-loader's isComponent validator only accepted vote 0|1, rejected all v0.2.1 payloads with any bearish vote. Fixed by Vega commit 9e76dc0; emissions were correct the whole time.
type: project
---

**What happened.** From v0.2.1 rollout (2026-09-22) through 2026-10-12,
`faractionradar.com/oil` rendered the pre-first-emission AWAITING
fallback despite Helios emitting correct, validated `weekly/current.json`
to GH-raw and R2 every weekday. Root cause was FAR-side: Vega's
`assertSignalComponents` validator at `lib/helios/types.ts:251` accepted
only `vote === 0 || vote === 1`. The 2026-10-09 LONG call had
`momentum.vote = -1` (from bot v3 seed 7's tri-state regime vote),
which failed validation. `tryFetchAndParse` caught the throw and
returned null, so the site fell back to AWAITING.

**Vega's fix (commit 9e76dc0 on FAR main):**
- `HeliosComponent.vote` widened to `-1 | 0 | 1`
- `isComponent` accepts -1
- `netVoteFromComponents` returns signed net (bulls − bears)
- `SignalMeter`/`meterState` work on signed net
- `FactCell` renders BEAR label + red accent for vote = -1

**What this means for Helios:**
- Our emission format is correct; nothing to change on our end.
- R2 secret wiring is no longer blocking (GH-raw fallback works);
  R2 is still a latency nice-to-have.
- Next weekly emission lands immediately on /oil without the stopgap
  seed script.
- Gate 7 clock was never affected — the emissions were valid; only the
  render path was broken. Shadow-window evidence under
  `results/shadow/*.json` on `origin/main` is unaffected.

**Vega's request:** For any future PROTOCOL changes that touch the
emitted-signal schema (new vote state, new component, renamed field),
ping ahead via the `arbaboil/boildt` commit message so Vega can update
the FAR validator before our emission flips the site to AWAITING.
Captured as a feedback memory + a step in the DATA-CONTRACT bump
checklist.

**Confirmed live render 2026-10-12 post-deploy:** LONG @ $91.65, 92%
confidence, bot_v3_seed7, 3 components confirming — matches the
2026-10-05-weekly entry Helios emitted on 2026-10-09.
