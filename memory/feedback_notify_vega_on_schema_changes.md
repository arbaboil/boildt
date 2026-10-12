---
name: Notify Vega via commit message before changing emitted-signal schema
description: FAR site-loader has a strict validator; any new vote state, new component, or renamed field must be flagged in a commit message before the emission lands, or the site renders AWAITING.
type: feedback
---

**Rule.** Before pushing any change that alters the schema of
`results/emitted/weekly/current.json` or `results/emitted/daily/current.json`
— new vote state (e.g., 2-strength bull `+2`), new component, renamed
field, changed component list — write a commit message that explicitly
flags the change for Vega.

Suggested commit header:
```
PROTOCOL vX.Y schema change — Vega validator update required

<description>

Vega: update isComponent in lib/helios/types.ts and whatever renderers
touch <field>. Site will fall to AWAITING on next cron if not updated
before <approximate_next_emission_timestamp>.

Agent: helios
```

**Why:** Between 2026-09-22 (v0.2.1 ship) and 2026-10-12, every live
weekly call was correctly emitted but silently rejected by FAR's
`assertSignalComponents` validator because it only accepted
`vote === 0 || vote === 1`. v0.2.1's tri-state votes (`-1` bearish /
`0` abstain / `+1` bullish) triggered the throw whenever any component
voted bearish; the site rendered the pre-first-emission AWAITING
fallback for ~20 days. Vega fixed it (commit 9e76dc0) after the Owner
flagged it, and asked us to ping ahead on future changes so this
doesn't repeat. See
`memory/project_helios_vega_awaiting_bug_2026-10-12.md`.

**How to apply:**
1. Pure *value* changes to existing fields (e.g., the `HELIOS_COT_ENABLED`
   flag flipping `vote_cot` from 0 to −1 or +1) do **not** need the
   Vega ping — tri-state is already supported post-9e76dc0.
2. Any change to the field *list*, *types*, or *introduction of a new
   discrete value* for an existing field (e.g., adding `+2` for
   STRONG_BUY if we move it from `read` into the vote space) **does**
   need the ping.
3. Also note the change in `docs/DATA-CONTRACT.md` under its
   "Schema version history" section with the FAR validator spot that
   needs updating.
4. Prefer a dedicated schema-only commit (don't bundle with unrelated
   logic) so the Vega ping line is easy to spot in `git log`.
