---
name: Helios launch-ready state (2026-09-22, post PROTOCOL v0.2.0 approval)
description: End-of-session-3-plus state. All Owner-blocked items resolved. Bot ships day 29 (2026-10-20). Vega handoff pack sealed. Only calendar time remains.
type: project
---

**Snapshot 2026-09-22 (session-3 extended, post-approval).** All four Owner-blocked items from the SESSION3-REPORT are RESOLVED:

1. **PROTOCOL v0.2.0** — LOCKED. Owner approved. `docs/PROTOCOL.md` bumped 0.1.0 → 0.2.0. Gate 2 (WR ≥ 50%) retired; replaced by Gate 2a (expectancy CI > 0) + Gate 2b (mean_r_net ≥ 0.05). Amendment logged.
2. **EIA API key** — WIRED. Stored in `.env` (gitignored). Master + features rebuilt with 3 EIA-derived cols. Seed 7 re-audited under v0.2.0 with EIA-present features: still PASS on all 3 slices.
3. **GitHub remote + daily cron** — LIVE. Repo `arbaboil/boildt` on GitHub. Push access working. CI runs on every push (green). `.github/workflows/daily.yml` fires at 21:00 UTC daily; first run 2026-09-22 succeeded, committed shadow log entry back to main.
4. **Vega handoff** — SEALED. `handoff-pack/` folder committed to the repo containing README + VEGA-MESSAGE + docs + evidence + sample-artifacts. Owner will relay `handoff-pack/VEGA-MESSAGE.md` to Vega on ship day.

**Ship candidate.** Bot v3 seed 7 (`results/bots/bot_v3_seed7_candidate.json`) passes strict PROTOCOL v0.2.0 on TRAIN + VAL + HOLDOUT. Supporting evidence: Brent cross-crude validation, 75/75 sensitivity perturbations robust, 3× cost-stress robust, Monte Carlo 98.9% pos year 0% ruin, regime-consistent (bull/chop/bear), permutation p ≤ 0.05 on all slices.

**Ship blocker: calendar time only.** Shadow window at 2/28 days on 2026-09-22. Expected clear 2026-10-20 (day 29). No Owner action required in the meantime — the daily cron accumulates shadow entries automatically.

**Live-flip mechanism.** `python scripts/emit_reads.py --live` flips WEEKLY out of shadow (direction becomes BUY/SELL/FLAT, shadow_mode=false). Daily brief stays shadow_only unless `--daily-live` is ALSO passed (which should stay off until a v0.3.0 daily-cadence Gate 5 fix lands — daily currently fails on TRAIN with 18.4R > 15R threshold).

**Test count.** 103 tests, all green. CI running clean on every push.

**How to apply.** Next session (~2026-10-20): (a) confirm `ship_readiness.json` shows `green_light: true` and `shadow.n_days >= 28`, (b) run `emit_reads.py --live` to flip weekly, (c) commit + push the live payload, (d) hand Owner the `handoff-pack/VEGA-MESSAGE.md` content for the Vega relay. If any shadow-log day shows drift outside the walk-forward envelope, pause and root-cause before flipping live.

**Post-launch v0.3.0 backlog.**
- Retune seed 7 with EIA-included features (Session 3 sweep on seeds 51-60 in progress at close of session)
- Fix daily-cadence Gate 5 (position-sizing tricks or regime-gated trading)
- News/geopolitics feed (GDELT) for supply-shock events
- Portfolio-of-bots: pair seed 7 with an orthogonal mean-reversion candidate
