# HELIOS handoff pack (for Vega)

**Status at end of Session 1 (2026-09-18):** NOT ship-ready. Scaffolding is
complete, engine v0.1 produces reproducible reads, one honest walk-forward
shows 6/10 folds positive (fails the 7/10 gate). Bot GA v1 is running.
Shadow window has not started. Do NOT integrate into `web/` yet.

This folder exists so that when a version DOES clear the gates, integration
is a single-session drop-in.

## What's here

- `weekly-call.schema.json` — JSON Schema for the weekly output
- `daily-brief.schema.json` — JSON Schema for the daily output
- `README-vega.md` — this file

## What will land here at ship time

- `engine_bundle/` — a self-contained Python module: given a feature
  parquet, emits a weekly-call JSON and a daily-brief JSON. One entrypoint.
- `bot/genome.json` — the evolved genome, with a `replay.py` and README
- `shadow_summary.json` — 4-week silent-live tape summary vs. walk-forward
  envelope (must be inside envelope to ship)
- `kill_switch.md` — kill-switch specifications matching FAR contract
  standards: emergency pause, per-member cap, priceStep bounds, daily-trade
  rate limit, pro-membership expiry check

## Integration checklist (do not check off — this is a template)

- [ ] Weekly-call clears gates 1–6 on TRAIN + VALIDATION + walk-forward
- [ ] Daily brief clears gates 1–6 OR is marked `shadow_only: true`
- [ ] Bot clears gates B1–B7 including fresh-seed retest
- [ ] Shadow log ≥ 4 weeks, in-envelope
- [ ] Owner has reviewed `docs/LAB-NOTEBOOK.md` for the honest audit trail
- [ ] Cost model version (locked in `docs/PROTOCOL.md`) copied here
- [ ] Kill-switch spec copied here
- [ ] Vega can regenerate every published number with a single command:
      `python scripts/pull_data.py && python scripts/build_features.py &&
       python scripts/backtest.py --engine <ver>`

## Contact

Helios has no direct channel to Vega. Route all questions through Owner
using the `message begin`/`message end` protocol.

Agent: helios
