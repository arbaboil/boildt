# Vega relay message — copy-paste this on ship day

**When to send:** on or after 2026-10-20 (day 29, once Gate 7 shadow window clears cleanly). Owner opens a Vega session and pastes the block below verbatim.

**How to send:** open Vega, paste the entire code block (including the `message begin` / `message end` fences). Vega will follow the FAR playbook.

**Prerequisite check before sending:**
1. Open `results/ship_readiness.json`. Confirm `verdict.green_light: true` and `shadow.n_days >= 28`.
2. Skim the last 4 shadow-log entries (`results/shadow/2026-10-*.json`). Confirm reads look sensible (no wild swings from calibration).
3. Then flip live: `python scripts/emit_reads.py --candidate results/bots/bot_v3_seed7_candidate.json --audit results/bots/bot_v3_seed7_candidate_audit.json --live` — this rewrites `results/emitted/*.json` with `shadow_mode: false`, `direction: BUY/SELL/FLAT`.
4. Commit + push that flip. Now paste this into Vega:

---

```
message begin ─────────────────────────────────────────────
To:   Vega
From: Helios (via FAR Owner relay)
Re:   HELIOS oil vertical — site integration handoff
Date: <FILL IN TODAY>

Vega — the oil vertical is ready for site integration. Bot v3 seed 7
cleared PROTOCOL v0.2.0 offline and cleared Gate 7 shadow (28 silent-
live days). Ship the weekly call live; daily brief stays shadow-only
pending its own gate clearance in a v0.3.0 patch.

Handoff pack location:
  Repo: https://github.com/arbaboil/boildt
  Folder: handoff-pack/
  Version: 1.0 (sealed on PROTOCOL v0.2.0 approval, 2026-09-22)

Please:
1. Read handoff-pack/README.md first.
2. Follow the checklist in handoff-pack/docs/HANDOFF.md.
3. Provision R2 buckets:
     helios-data-staging  (public-read, CORS = FAR site origins)
     helios-data-prod     (same)
4. Add cron in the site build pipeline that pulls the latest
   handoff-pack/sample-artifacts/emitted/* shape from arbaboil/boildt
   (or from R2 once the daily cron uploads there — Option A vs B in
   HANDOFF.md). Weekly refresh 21:15 UTC Fri, daily 17:00 UTC weekdays.
5. Wire a "HELIOS says" panel on the members oil tab. Under
   shadow_mode:true (never for the initial live ship, but keep the
   render path for future re-calibrations) show "HELIOS calibrating".
   Under shadow_mode:false show the live BUY / SELL / FLAT call with
   confidence bar and level guidance (levels.stop_atr_mult etc.).
6. Wire kill-switch check per DEPLOY-PLAN.md. Site must suppress
   render if provenance.kill_switch_engaged is true.
7. Wire stale-data banner: weekly published_utc older than 8 days OR
   daily older than 2 days shows "HELIOS data stale".

Questions and edge cases you'll want to know about are in the
evidence/ folder — sensitivity, Brent cross-validation, cost stress,
Monte Carlo. Everything is audited and pass/fail transparent.

If any schema field is unclear or you want to propose a change to
the contract, message me via Owner. Do not silently deviate — the
loader tests will catch mismatches but explicit is better.

— Helios
message end ─────────────────────────────────────────────
```

---

## After Vega acks

Vega will typically respond within one message. Common asks:

- **"Provisioning R2 — what's the target ID?"** — you name the buckets when
  you provision. Any name works. Once provisioned, tell me the bucket
  IDs and I'll update `docs/DEPLOY-PLAN.md`.

- **"What auth for the daily cron upload?"** — GitHub Secrets for
  Cloudflare R2 API token. Follow AXIS's pattern: `AXIS_R2_TOKEN` →
  `HELIOS_R2_TOKEN`.

- **"Can I get TypeScript types for the contract?"** — I can write
  those from `docs/DATA-CONTRACT.md` in ~5 min. Ask me and I'll
  produce a `helios-contract.d.ts` file in the next round.

- **"What's the fallback if the daily cron misses a day?"** — stale
  banner (see step 7). No other fallback — better to show "stale"
  than a false-live signal.

- **"Any known regressions on the horizon?"** — daily brief still
  fails Gate 5 (18.4R max DD vs 15R threshold). Will retry in v0.3.0
  after we look at position-sizing tricks. Weekly call is clean.

Ping me back through the Owner relay with any of these and I'll
build the exact patch.
