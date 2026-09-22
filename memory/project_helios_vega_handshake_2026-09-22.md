---
name: Helios ↔ Vega pre-ship coordination complete (2026-09-22)
description: Full handshake with Vega done same-day. R2 buckets provisioned, site loader shipped, kill-switch mirroring live. Waiting on Owner-supplied R2 credentials + calendar time.
type: project
---

**Coordination completed 2026-09-22.** Full 4-message handshake with Vega done same day as pre-ship heads-up (see `handoff-pack/VEGA-MESSAGE.md` for the initial). Both sides code-complete + deployed to their respective infra.

**Vega side (deployed to prod):**
- R2 buckets provisioned:
  - staging → `https://pub-021e64832d994b38ade41c3a9f3ba7f2.r2.dev`
  - prod    → `https://pub-b3a50879eef9424bae993b9cce189451.r2.dev`
- Site loader at `web/lib/helios/` (types.ts + data.ts). Reads via `NEXT_PUBLIC_HELIOS_TARGET` env var, default staging, Owner flips to prod on ship day.
- Public `/oil` page live with strict precedence: kill-switch → stale → shadow → live. Renders "Awaiting first emission" empty state until HELIOS uploads.
- Render-time kill-switch fetch of `admin/killswitch.json` implemented (`getHeliosKillSwitch()` in `lib/helios/data.ts`) with 30s revalidate + fail-open on fetch error.
- Backtest strip covers TRAIN/VAL/HOLDOUT + component-vote breakdown for 7 components including null_components handling.
- Daily brief intentionally NOT wired yet (waits for v0.3.0 Gate 5 fix at daily cadence).
- Stale banner correctly fires only when BOTH weekly + daily miss for 8 days (Vega's insight — daily re-emit keeps `published_utc` fresh so 8-day-stale is a true dead-cron signal, not a single-cadence blip).

**Helios side (committed to arbaboil/boildt):**
- Commit `4f07231`: R2 upload wired into `.github/workflows/daily.yml` — `awscli` against R2 S3-compat endpoint, uploads weekly/current.json + daily/current.json + backtest/summary.json with `Content-Type: application/json` and `Cache-Control: public, max-age=30`. Skips gracefully if secrets missing.
- Commit `7e1df52`: `admin/killswitch.json` also mirrored to R2 for Vega's render-time check.
- `docs/DEPLOY-PLAN.md` bumped 0.1.0 → 0.2.0 with both bucket URLs baked in.

**Owner-blocked (final remaining piece before Helios's cron does the first real R2 upload):**
Owner must generate a Cloudflare R2 API token (Object Read & Write, scoped to both buckets, permanent TTL) and add 3 GitHub Secrets to `arbaboil/boildt`:
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Once added, next 21:00 UTC cron will do the first upload; Vega's page flips from "Awaiting first emission" to SHADOW banner within a minute.

**Vega's shadow-drift fallback offer:** if the shadow window drifts and I pause, Vega will drop a "HELIOS in extended shadow" note above the calibrating banner so members aren't confused about the timeline. Ping via Owner if that path is needed.

**Ship day (2026-10-20) sequence unchanged:** verify green_light in ship_readiness.json → flip weekly via `--live` in daily.yml → next cron writes live payload to staging → Owner flips `NEXT_PUBLIC_HELIOS_TARGET=prod` on site → Vega redeploys. `handoff-pack/VEGA-MESSAGE.md` has the go-live message text. Owner will also need a second workflow run (or a manual `wrangler r2 object cp`) to promote artifacts from staging → prod bucket that day.

**How to apply next session.** If Owner has added the R2 secrets before Oct 20, artifacts are already flowing to staging by that date — nothing extra to do besides the live flip + prod promotion + final Vega message. If not, add them Oct 20 morning and the same-day cron does staging + prod in sequence.
