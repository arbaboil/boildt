# HELIOS — Data Contract (schemas for FAR site integration)

Version: 0.1.0 (draft — locks on first shadow-window entry)
Last edited: 2026-09-22

Modeled on AXIS's contract in `C:\dev\FarACtionRadar\v16build\web\axis-engine\src\emit.ts`.
Field names + shapes mirror AXIS where semantics match. Deviations
called out inline.

## Artifacts

Vega integration target: R2 bucket `helios-data-{staging|prod}`, keys:

| Key | Cadence | Purpose |
|---|---|---|
| `weekly/current.json` | 1× per week (Fri close UTC) | Current weekly regime call |
| `daily/current.json` | 1× per business day (17:00 UTC) | Daily brief; shadow-only for now |
| `history/index.json` | on each resolve | Index of resolved calls |
| `history/{week_of}.json` | on each new week | Per-week detail |
| `backtest/summary.json` | landed once per version | Aggregated OOS stats |

All objects are public-read JSON, `Content-Type: application/json`,
`Cache-Control: public, max-age=30, s-maxage=30`. Ownership: `Agent: helios`.

## `weekly/current.json` schema

```jsonc
{
  "type": "call",
  "schema_version": 1,
  "instrument": "WTI",          // primary; "brent" reserved for future
  "week_of": "2026-09-14",      // Mon UTC ISO
  "week_end": "2026-09-20",     // Sun UTC ISO
  "signal_date_utc": "2026-09-19T21:15:00Z",
  "published_utc":   "2026-09-22T14:00:00Z",

  "direction": "LONG",          // "LONG" | "SHORT" | "FLAT" | "SHADOW"
  "shadow_mode": true,          // true until PROTOCOL Gate 7 completes

  "current_price": 93.31,
  "atr_20d": 2.14,

  "signal_components": {
    "trend":    { "vote": 1, "weight": 0.61,  "value": 0.043 },
    "momentum": { "vote": 1, "weight": 1.32,  "value": 0.028 },
    "vol":      { "vote": 0, "weight": 2.10,  "value": 0.021 },
    "curve":    { "vote": 1, "weight": 3.83,  "value": 0.82  },
    "cot":      { "vote": 0, "weight": 0.98,  "value": null },
    "eia":      { "vote": 0, "weight": 1.13,  "value": null },
    "macro":    { "vote": 0, "weight": 2.07,  "value": -0.014 }
  },
  "confidence": 82,             // 0-100 int, matches AXIS convention
  "score": 0.478,               // signed float; sign matches direction

  "message": "3 components confirming long bias; 82% confidence.",
  "primary_risk": {
    "sentence": "Primary risk: DXY strength this week could reverse the crack-spread bid.",
    "severity": "med",          // "high" | "med" | "low"
    "trigger": null             // future: named regime-flip trigger
  },

  "provenance": {
    "candidate": "bot_v3_seed7_candidate",
    "protocol_version": "0.1.0",
    "genome_hash": "sha256:...",
    "coverage": 0.8247,         // fraction of votes present
    "null_components": ["vol", "cot", "eia"],
    "helios_version": "0.1.0"
  },

  "live_pnl_pct": null,         // set by live resolver, null at emit
  "live_updated_utc": null,
  "outcome": null,              // "TARGET" | "STOP" | "TIME" once resolved

  "levels": {
    "stop_atr_mult": 0.754,
    "target_atr_mult": 4.693,
    "hold_days_max": 11,
    "suggested_entry_price": 93.31,
    "suggested_stop_price_at_entry":    91.70,
    "suggested_target_price_at_entry": 103.35
  }
}
```

Notes:
- `direction: "SHADOW"` returned whenever `shadow_mode: true` — site
  loader renders "HELIOS calibrating" instead of the underlying read.
- `hold_days_max`: from the candidate's `max_hold_days`. Renamed from
  AXIS `hold_days` to signal that HELIOS uses a max-hold, not a
  fixed-hold.
- Suggested prices are at emit-time `current_price`. Users entering
  later re-anchor themselves.
- `provenance.candidate` matches the JSON stem in `results/bots/`.

## `daily/current.json` schema

Same shape as `weekly/current.json`, with:
- `type: "brief"` instead of `"call"`
- `week_of` / `week_end` → replaced with `as_of`
- Daily brief is `shadow_only: true` by default until it clears
  gates 1, 2 (v0.2.0 g2a+g2b), 5, 6 at daily cadence. Currently
  Gate 5 fails on daily.

## `history/index.json` schema

```jsonc
{
  "type": "history_index",
  "schema_version": 1,
  "resolved_calls": [
    { "week_of": "2026-08-31", "outcome": "TARGET", "r_net": +5.03 },
    { "week_of": "2026-09-07", "outcome": "STOP",   "r_net": -1.00 },
    { "week_of": "2026-09-14", "outcome": "TIME",   "r_net": +0.34 }
  ]
}
```

## `backtest/summary.json` schema

Static per candidate. Emitted once when a new PROTOCOL version + candidate
lands.

```jsonc
{
  "type": "backtest_summary",
  "schema_version": 1,
  "candidate": "bot_v3_seed7_candidate",
  "protocol_version": "0.1.0",
  "slices": {
    "TRAIN":       { "n": 238, "wr": 0.38, "mean_r": 1.14, "sharpe": 1.60, "sharpe_ci_low": 1.14, "max_dd_r": 10.7, "perm_p": 0.000 },
    "VALIDATION":  { "n":  89, "wr": 0.33, "mean_r": 0.88, "sharpe": 1.24, "sharpe_ci_low": 0.43, "max_dd_r": 10.2, "perm_p": 0.003 },
    "HOLDOUT":     { "n":  58, "wr": 0.36, "mean_r": 0.97, "sharpe": 1.49, "sharpe_ci_low": 0.61, "max_dd_r":  6.8, "perm_p": 0.008 }
  },
  "walkforward": { "k": 10, "positive_expectancy_folds": 10, "pass_7of10_rule": true },
  "regime_by_regime": {
    "bull": { "n": 166, "mean_r": 0.86 },
    "chop": { "n":  62, "mean_r": 1.58 },
    "bear": { "n":  99, "mean_r": 1.11 }
  }
}
```

## Shadow-mode contract

- While Owner has not signed PROTOCOL v0.2.0 amendment (or the candidate
  has not completed its 4-week silent-live window), all published
  artifacts carry `shadow_mode: true` and `direction: "SHADOW"`.
- Site UI renders "HELIOS calibrating — signals go live after N more
  weeks." N is computed by the site from `shadow_start_utc` in
  provenance (to be added when shadow starts).

## Kill-switch contract (see docs/DEPLOY-PLAN.md)

Site loader must check `provenance.kill_switch_engaged` before rendering.
When true, render "HELIOS paused" and swallow the read. Kill-switch is
Owner-only via a dedicated R2 key `admin/killswitch.json`.

## Backwards compatibility

- `schema_version: 1` will hold as long as fields are only added, never
  removed. Adding fields is safe; site can ignore unknown keys.
- Any removal or type change bumps schema_version and MUST be
  co-published with a schema deprecation window (2+ weeks).
