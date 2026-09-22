# HELIOS — Deploy plan + kill-switch spec

Version: 0.1.0-draft
Owner: FAR Owner (kill-switch access) + Vega (deploy operator)

## Ship prerequisites

**Cannot ship live** until ALL of the following are true:

1. **PROTOCOL** — either v0.1.0 (Bot passes all 7 gates) or v0.2.0
   signed by Owner. Bot v3 seed 7 currently fails v0.1.0 gate 2 (WR)
   and passes proposed v0.2.0.
2. **Gate 7** — 4 consecutive weeks of silent-live shadow with
   direction + suggested levels landing inside the walk-forward fold
   envelope (median WR ± 10pp; median mean-R inside p25/p75 bootstrap).
3. **Monte Carlo** — `results/monte_carlo/<candidate>_mc.json` shows
   `prob_ruin < 1%` under `stress_extra_5bps`. Seed 7 shows 0.00%.
4. **Data freshness monitor** — cron on `pull_data.py` succeeds ≥ 5 of
   last 7 days. Alert when a source (FRED/Yahoo/COT) misses 2+ days.
5. **Site loader** — passes handoff test plan in `HANDOFF.md`.

## Deploy sequence

Copy the AXIS deploy pattern verbatim, with one addition (kill-switch
pre-flight):

1. **T-2 weeks**: Owner signs PROTOCOL v0.2.0 (or reject → return to lab).
2. **T-2 weeks**: candidate audit re-run and archived (`scripts/candidate_audit.py`).
3. **T-1 week**: Vega provisions R2 buckets + env vars per HANDOFF.
4. **T-1 week**: staging deploy. HELIOS artifacts pushed to
   `helios-data-staging`. Site staging renders shadow banner.
5. **T-0**: Owner runs `admin/killswitch.json = {"enabled": false}` on
   prod bucket. Vega flips `HELIOS_R2_TARGET = "prod"`. First live
   weekly call emits.
6. **T+4 weeks**: shadow → live transition (Owner flips
   `HELIOS_SHADOW_MODE = "false"`). Site loader drops the calibration
   banner and starts publishing directional signals to members.
7. **T+8 weeks**: first performance retro against walk-forward envelope.
   Amend if drift.

## Kill-switch spec

### Purpose

An always-available, single-action, side-channel switch that instantly
suppresses HELIOS from member view without requiring a code change or
Worker redeploy. Owner-only. Covers:

- Data source outage or corruption (bad WTI feed → wrong signals)
- Model drift or extreme regime (2020-negative-oil-scale event)
- Legal or compliance pause request
- Any "kill it now" scenario

### Contract

The switch lives at `admin/killswitch.json` in **both** staging and
prod R2 buckets. Contents:

```json
{
  "enabled": false,
  "reason": null,
  "set_by": null,
  "set_at_utc": null,
  "expires_utc": null
}
```

To engage: overwrite with

```json
{
  "enabled": true,
  "reason": "brief description",
  "set_by": "owner_email_or_id",
  "set_at_utc": "2026-09-22T18:00:00Z",
  "expires_utc": null
}
```

`expires_utc` optional — when set, kill-switch auto-releases (site loader
still checks the key each fetch).

### HELIOS-side behavior

`scripts/emit_reads.py` reads `admin/killswitch.json` (if the file is
provided via env or a local mirror). When `enabled: true`:

- `provenance.kill_switch_engaged: true`
- `direction: "SHADOW"` (regardless of underlying read)
- `message` overridden with `"HELIOS paused — {reason}"`
- Everything else in payload preserved so post-mortem can inspect the
  read that would have shipped.

### Site-loader behavior

Site MUST check `provenance.kill_switch_engaged` before rendering.
When true:

- Render "HELIOS paused" banner with `reason` if non-empty.
- Suppress the signal card and the levels box.
- Suppress the daily brief.
- Backtest summary + history tabs remain visible (they are historical).

### Cadence

Kill-switch check runs at both emit-time (HELIOS) and render-time (site).
Emit-time suppression prevents a wrong signal from being cached; render-
time suppression handles the case where a live artifact was already
uploaded before the switch flipped.

Recommended TTL: 30s cache on `admin/killswitch.json` at the site edge.
Instant propagation is not a requirement — 30s window is acceptable.

### Access control

- Only Owner has write access to `admin/killswitch.json`. Vega has
  read-only.
- Rotate credentials if the kill-switch is engaged for a non-drill
  reason.
- All engage / disengage events audit-logged to `admin/killswitch.audit.log`
  (append-only R2 object).

## Operator-ban / role-separation

Copied from FAR contracts (`FarStrike.sol:339` — "operator cannot play"):

- **Helios agent** publishes signals + reads. Cannot receive live PnL.
  Isolation prevents "agent trades against its own signal" scenarios.
- **Vega** publishes to R2 + operates infra. Cannot trigger the
  kill-switch alone (Owner-only write on the admin key).
- **Owner** holds the kill-switch and PROTOCOL amendment authority.
  Does not run the HELIOS engine day-to-day (Helios agent does).

## priceStep-style bounds (defensive)

The engine emits `suggested_stop_price_at_entry` and
`suggested_target_price_at_entry`. To prevent a corrupt ATR value
from producing absurd levels (like "stop at $0.01"), emit_reads enforces:

- `suggested_stop_price_at_entry` must be within `[0.5 × current_price,
  1.5 × current_price]`. If ATR blows out, emit direction = FLAT and
  set `provenance.bounds_violated = true`.
- `atr_20d` must be within `[0.5%, 10%]` of `current_price`. Same
  fallback if violated.

Both bounds live in `src/util/config.py` and are locked via PROTOCOL
version. Any change bumps version.

## Monitoring

Minimum daily heartbeat via cron:

- `pull_data.py` succeeds (data freshness < 2 BD).
- `emit_reads.py` writes both `weekly/current.json` and `daily/current.json`.
- `admin/killswitch.json.enabled` value (auditable diff).

Alert channels: email to Owner on:
- 2+ consecutive data pull failures
- kill-switch flip (either direction)
- weekly emit fails 2+ weeks running
- shadow window drift metric > 1σ from walk-forward envelope

## Rollback

- **Immediate:** flip kill-switch on. Signals go dark within 30s.
- **Version rollback:** promote a previous `results/emitted/backtest/summary.json`
  by re-running `emit_reads.py --candidate <previous_candidate>` and
  pushing. Site loader picks up the new artifact within 30s.
- **Full rollback:** `HELIOS_R2_TARGET = "staging"` → prod site stops
  fetching. Emergency-only; requires site redeploy.
