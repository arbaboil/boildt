# HELIOS Handoff Pack (Oil vertical)

**From:** Helios (via FAR Owner)
**To:** Vega
**Date sealed:** 2026-09-22
**Ship day (target):** 2026-10-20 (day 29 = shadow window close)
**Version:** 1.0 — sealed on PROTOCOL v0.2.0 approval

This folder contains everything you need to wire HELIOS into the FAR
site. Structure mirrors what you already know from the AXIS handoff.

## 30-second orientation

- **Product:** weekly + daily oil regime call (BUY / SELL / FLAT) with
  confidence, level guidance, and a 7-component vote breakdown.
- **Underlying candidate:** `bot_v3_seed7_candidate` (a genetically
  evolved trend/momentum/curve consensus).
- **Ship status on this date:** all offline gates PASS under PROTOCOL
  v0.2.0. Gate 7 (silent-live shadow) is running via a daily GitHub
  Actions cron. Expected clear: 2026-10-20.
- **Emit shape:** identical to AXIS's `emit.ts` output, adapted for
  oil. See `docs/DATA-CONTRACT.md`.

## Read these first (in order)

1. **`docs/HANDOFF.md`** — the integration checklist you follow.
2. **`docs/DATA-CONTRACT.md`** — the JSON schemas you consume.
3. **`docs/DEPLOY-PLAN.md`** — kill-switch, monitoring, rollback.
4. **`docs/PROTOCOL.md`** — the ship gates (v0.2.0, locked).
5. **`docs/SESSION3-REPORT.md`** — all the evidence in one place, if
   you want to see WHY seed 7 was picked.

Optional (context, not required):
- `docs/MISSION.md`, `docs/ARCHITECTURE.md`, `docs/RESEARCH-PLAN.md`
- `docs/REALISM.md` — fidelity score (monotonic ratchet)
- `docs/ENGINE-ONLY-SHIP.md` — the Plan-B path (currently unused; keep
  for reference if bot line ever regresses)

## What ships to the site

Contract-compliant JSON at:

```
weekly/current.json
daily/current.json
backtest/summary.json
```

Live samples in `sample-artifacts/emitted/` — those are exactly what
your R2 loader will fetch. Schemas locked in `docs/DATA-CONTRACT.md`.

## What NOT to do

- Do **not** touch `bot_v3_seed7_candidate.json` in `evidence/`. It is
  the *audited* genome and is the reference the shadow window is being
  validated against. Any change resets the shadow clock.
- Do **not** flip `shadow_mode` to `false` before day 29. Helios will
  do that itself once Gate 7 clears (single-config flip in
  `scripts/emit_reads.py`, propagates on next cron run).
- Do **not** ship the daily brief live yet. Currently `shadow_only:
  true` — it fails daily-cadence Gate 5 (max_dd 18.4R vs 15R
  threshold). Weekly-call ships first; daily follows in a v0.3.0
  patch when it clears.

## Evidence bundle (for your review or a member-facing "why should I
trust this?" page)

Everything in `evidence/`:

| File | What it proves |
|---|---|
| `bot_v3_seed7_candidate.json` | The genome. Vote weights, thresholds, R:R. |
| `bot_v3_seed7_candidate_audit.json` | Passes all 6 automatable v0.2.0 gates on TRAIN + VAL + HOLDOUT. |
| `bot_v3_seed7_candidate_brent_validation.json` | Strategy generalizes to Brent (independent instrument). |
| `bot_v3_seed7_candidate_sensitivity.json` | 75 genome perturbations, zero flip VAL Sharpe CI negative — robust. |
| `bot_v3_seed7_candidate_cost_stress.json` | Positive mean R on all slices under 3× baseline costs. |
| `bot_v3_seed7_candidate_holdout_drift.json` | Quarterly holdout WR + R breakdown; no unrecoverable drift. |
| `bot_v3_seed7_candidate_ablation.json` | Feature-importance drop-one; no single feature is load-bearing. |
| `bot_v3_seed7_candidate_mc.json` | 10k Monte Carlo forward paths: 98.9% pos year, 0.00% ruin. |

## Repo access (for building your loader)

If you want to script-generate types from the contract or copy the
emitter code:

```
git clone https://github.com/arbaboil/boildt.git
```

Everything HELIOS produces is in `results/emitted/`, refreshed daily
by the GH Actions cron `.github/workflows/daily.yml`.

## Contact

No direct AI-to-AI channel. Any questions come back through FAR Owner
who relays. Message format follows the FAR playbook (`message begin
─── / message end ───`).

Good hunting.
