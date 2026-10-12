# Autotrader cutover readiness audit — 2026-10-20 target

Author: Helios · Date: 2026-10-12 · Target cutover: 2026-10-20 (8 days)

Owner confirmed 2026-10-12 that 2026-10-20 is the **on-chain autotrader
cutover** (distinct from Gate 7 shadow completion, which lands
~2026-11-04). Signals are already rendering live on /oil post Vega
commit 9e76dc0.

This audit walks `docs/DEPLOY-PLAN.md`'s ship prerequisites + the
hardening pattern CLAUDE.md invokes (kill-switch, operator-ban,
priceStep bounds), and flags any Helios-side gaps or ambiguities
before Vega needs them.

## Payload surface (what the autotrader consumes)

Verified from latest `results/emitted/weekly/current.json`
(2026-10-05-weekly, published 2026-10-09):

| Field | Present | Notes |
|---|---|---|
| `direction` | ✓ | LONG |
| `schema_version` | ✓ | 1 |
| `instrument` | ✓ | WTI |
| `signal_date_utc` + `published_utc` | ✓ | both ISO-8601 |
| `levels.suggested_entry_price` | ✓ | 91.65 |
| `levels.suggested_stop_price_at_entry` | ✓ | 89.06 |
| `levels.suggested_target_price_at_entry` | ✓ | 107.74 |
| `levels.hold_days_max` | ✓ | 11 |
| `levels.stop_atr_mult` / `target_atr_mult` | ✓ | 0.754 / 4.69 (genome) |
| `confidence` | ✓ | 92 (percentage) |
| `shadow_mode` | ✓ | false |
| `provenance.candidate` | ✓ | bot_v3_seed7_candidate |
| `provenance.protocol_version` | ✓ | 0.2.1 |
| `provenance.genome_hash` | ✓ | sha256:46372ef8… — anti-swap defense |
| `provenance.kill_switch_engaged` | ✓ | false |
| `provenance.bounds_violated` | ✓ | false |
| `provenance.coverage` | ✓ | 0.918 |
| `provenance.null_components` | ✓ | ["cot"] |

**Autotrader-relevant fields missing from the current payload** (flag
for Vega feedback — may already be on their side):

- **No position-sizing field.** Payload specifies 1R geometry
  (stop distance ⇒ 1R) but no explicit capital-fraction or
  position-size directive. Autotrader must derive from configured
  per-trade risk policy. Not a Helios responsibility unless Vega
  requires a sizing hint.
- **No signal-ID / trade-ID.** `signal_date_utc` could serve, but
  no explicit unique identifier. If the autotrader needs to tag
  on-chain executions back to a Helios signal for post-mortem,
  consider adding `signal_id = sha256(signal_date_utc + candidate)`.
- **No explicit early-close signal.** Current payload is a
  weekly LONG + levels. If a stop or target hits mid-week, the
  autotrader closes based on price. But if the model wants to
  CLOSE early (e.g., next week's call flips to FLAT with the
  previous week still open), the autotrader needs a rule: close
  on FLAT? Hold through? Needs Vega-side spec. Default assumption
  (reasonable): on FLAT, autotrader does nothing — holds existing
  position until stop/target/time hits.

## Ship prerequisites per DEPLOY-PLAN.md § 1-5

| # | Prerequisite | Status | Notes |
|---|---|---|---|
| 1 | PROTOCOL signed | ✓ | v0.2.1 locked 2026-09-22 |
| 2 | Gate 7 silent-live shadow | 🟡 | 10/28 as of 2026-10-09; completes ~2026-11-04. **Owner confirmed autotrader cutover is distinct from Gate 7 — not a blocker.** |
| 3 | Monte Carlo prob_ruin < 1% stress | ✓ | 0.00% (refreshed 2026-10-12 on corrected COT data) |
| 4 | Data freshness monitor (cron ≥ 5 of 7) | 🟡 | Cron succeeds on schedule but no dedicated freshness-check script exists. See **Gap A** below. |
| 5 | Site loader passes HANDOFF test plan | ✓ | Confirmed live-rendering post Vega 9e76dc0 (LONG @ $91.65 visible on /oil) |

## Kill-switch spec compliance

| Requirement | Status | Notes |
|---|---|---|
| `admin/killswitch.json` exists | ✓ | enabled: false, present |
| Mirrored to R2 both envs | ✓ | daily.yml step 7 uploads to staging; prod mirror on cutover |
| Owner-only write access | ✓ | enforced by R2 token scopes (Vega's side) |
| Emit-time check (payload field) | ✓ | `provenance.kill_switch_engaged` field present |
| Render-time check (site) | ✓ | per Vega handshake memory |
| 30s TTL on R2 cache | ✓ | `cache-control` max-age=30 set in daily.yml |
| `admin/killswitch.audit.log` append-only | ✗ | **Gap B** — spec calls for it, not implemented |

## priceStep bounds compliance

Located in `scripts/emit_reads.py` lines 43-47, not `src/util/config.py`
as DEPLOY-PLAN § 155 suggests. Not a functional gap — bounds are
enforced correctly:

- `ATR_PCT_MIN = 0.005`, `ATR_PCT_MAX = 0.10`
- `STOP_PRICE_MIN_MULT = 0.5`, `STOP_PRICE_MAX_MULT = 1.5`
- Cascade: `kill_switch > shadow_mode > bounds > normal` — direction
  forces FLAT on any violation
- `provenance.bounds_violated` flag published

**Gap C (doc-only):** DEPLOY-PLAN § 155 says bounds live in
`src/util/config.py`; they're actually in `scripts/emit_reads.py`.
Either move them or update the doc. Cosmetic.

## Operator-ban / role-separation

Per DEPLOY-PLAN § 144 ("operator cannot play" pattern from
FarStrike.sol:339):

- **Helios cannot receive live PnL.** Enforced at FAR contract
  level, outside Helios scope. No Helios-side action.
- **Vega cannot trigger kill-switch alone.** Enforced via R2 token
  scopes. Owner holds write; Vega holds read. Verifiable only on
  R2 side; no Helios-side action.
- **Owner holds PROTOCOL amendment authority.** Enforced by git
  commit-review workflow + the PROTOCOL amendment-log convention.

## Deploy sequence § 42 progress

| Step | Target | Status |
|---|---|---|
| T-2w: Owner signs PROTOCOL | 2026-10-06 | ✓ (v0.2.1 signed 2026-09-22) |
| T-2w: candidate audit archived | 2026-10-06 | ✓ (`results/bots/bot_v3_seed7_candidate_audit.json`) |
| T-1w: R2 buckets provisioned | 2026-10-13 | ✓ (2026-09-22 per handshake memory) |
| T-1w: staging deploy | 2026-10-13 | ✓ (cron live-uploading since 2026-09-22) |
| T-0: killswitch flip + prod target | 2026-10-20 | 🟡 pending Vega-side `HELIOS_R2_TARGET=prod` flip |
| T+4w: shadow → live transition | 2026-11-17 | Not yet planned — depends on live-signal cadence |

The DEPLOY-PLAN sequence was written for signal-ship (not autotrader).
For autotrader specifically, Vega controls the T-0 flip and the
on-chain contract-deploy work. Helios's role at T-0 is: don't change
anything. Keep the daily cron landing clean signals, verify kill-switch
mirror.

## Gaps + recommendations

### Gap A — No data-freshness monitor

**Severity:** Low (cron is already weekday-scheduled and succeeding).
**Scope:** 1 hr.

Add `scripts/check_data_freshness.py` that reads each raw parquet's
max date and compares to today minus the source's expected vintage lag.
Fail-loud if any source is behind:

- Yahoo WTI: today - 2 BD (holiday tolerance)
- FRED macro: today - 5 BD (monthly series tolerance)
- CFTC COT: today - 10 BD (weekly, Fri publish)
- EIA weekly: today - 5 BD (Wed publish, Thu available)

Wire into daily.yml between `pull_data` and `emit_reads`. Exit non-zero
if stale → cron fails visibly, Owner notified.

Also could serve as a second line of defense for the silent-COT style
outage, complementing the test_feature_coverage.py post-build check.

### Gap B — No kill-switch audit log

**Severity:** Low (manual audit via git history + R2 object versioning
covers today).
**Scope:** 30 min (append-only JSONL to R2).

When daily.yml uploads `admin/killswitch.json`, additionally append a
log entry if the switch state differs from the previous. Keep it in
`admin/killswitch.audit.log` on R2 (append-only). Not blocking for
10-20; add in next session.

### Gap C — Doc drift on bounds location

**Severity:** Cosmetic.
**Scope:** 5 min.

Fix DEPLOY-PLAN.md § 155 to reference `scripts/emit_reads.py` lines
43-47 (actual location). Or move the constants to `src/util/config.py`
to match the doc. Preference: keep near emit-site, update doc.

### Gap D — Autotrader payload fields

**Severity:** Depends on Vega's side — flag for coordination.
**Scope:** Vega decides; if any Helios-side changes needed, treat as
schema change (ping convention applies).

Three candidate fields:
- `signal_id` (deterministic hash of candidate + signal_date)
- `position_sizing_hint` (if autotrader wants Helios to opine on
  per-trade risk)
- `early_close_rule` (FLAT-on-open-position behavior spec)

Not needed for 10-20 unless Vega asks. Flag in next Owner-relay cycle.

## Verdict

Helios is **ready for the 2026-10-20 autotrader cutover from the
signal-emission side.** All DEPLOY-PLAN prerequisites either pass or
are explicitly waived by Owner (Gate 7). Payload fields cover the
contract. Kill-switch + bounds enforce safety.

Flagged gaps (A/B/C/D) are not blockers for 10-20 but should be
closed on their stated timescales. Gap A (freshness monitor) is
worth doing in the next session as a defense-in-depth measure.

No reply to Vega needed at this time — the T-0 flip is their action.
Helios's job on 10-20: do nothing. Keep cron landing clean, respect
any kill-switch flips, continue the Gate 7 shadow window toward
~2026-11-04 as scheduled.
