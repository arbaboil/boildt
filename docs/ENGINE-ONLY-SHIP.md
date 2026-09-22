# HELIOS — Engine-only ship path (fallback if PROTOCOL v0.2.0 rejected)

**Status:** Fallback plan. Only relevant if Owner declines to sign
`docs/PROTOCOL_v0.2.0_DRAFT.md`.

**Author:** Helios (2026-09-22, session 3)

## Why this doc exists

PROTOCOL v0.1.0 blocks the bot v3 seed 7 ship on Gate 2 (WR ≥ 50% on
simulated trades). PROTOCOL v0.2.0 replaces Gate 2 with a
payoff-adjusted invariant (mean_r_net ≥ 0.05). Session 3 evidence
(SESSION3-REPORT.md) shows v0.2.0 is the only path to any bot ship.

If Owner rejects v0.2.0, the **bot is deferred** — but the **engine
can still ship as a signal-only product**: weekly call + daily brief,
member reads BUY/SELL/FLAT and acts however they want. No trade
config, no stops, no targets.

## The engine-only signal quality story

Bot v3 seed 7's VoteConfig, evaluated as a SIGNAL (not as trades)
against forward WTI returns:

| Slice | Coverage | Stability | 5d directional accuracy (WR-analog) | IC 5d | IC 20d |
|---|---|---|---|---|---|
| TRAIN 2001-2018 | 40% | 90% | **54.4%** | +0.043 | +0.073 |
| VAL 2019-2023 | 57% | 87% | **58.1%** | +0.075 | +0.135 |
| HOLDOUT 2024-2026Q3 | 62% | 87% | **52.4%** | +0.083 | +0.056 |

**Every slice: directional accuracy > 50%.** IC positive across all
short/medium horizons. Source: `scripts/engine_signal_quality.py`,
artifact `results/engine_signal_quality.json`.

The engine's READ is directionally correct >50% of the time on all
three slices. The bot's TRADE fails Gate 2 because the trade adds
stops/targets that filter differently — that's a mechanics issue, not
a signal-quality issue.

## What ships in engine-only mode

- `results/emitted/weekly/current.json` — weekly call (`direction ∈
  {BUY, SELL, FLAT}`, confidence 0-100, signal components, current
  price, key levels).
- `results/emitted/daily/current.json` — daily brief (same shape).
- `results/emitted/backtest/summary.json` — historical
  weekly-signal performance summary for context.

All emitter code already exists (`scripts/emit_reads.py`). Contract
schemas locked in `docs/DATA-CONTRACT.md`.

Site UX: identical to AXIS on BTC — the "HELIOS says" panel with the
current call, confidence bar, and level guidance. Members interpret
and trade themselves.

## What does NOT ship in engine-only mode

- Bot / on-chain trading agent. Deferred until v0.2.0 signed or an
  alternative bot strategy passes v0.1.0 strict.
- Trade-level backtest cards (Sharpe, WR at trade level, max_dd, R-per-
  trade). Would confuse the story since engine-only doesn't trade.
- Kill-switch bounds on suggested stops/targets. Engine-only doesn't
  emit them. (Kill switch still applies to the direction call itself.)

## Engine-only ship gates (proposed)

| # | Gate | Threshold | Seed-7 evidence |
|---|---|---|---|
| E1 | Read-level directional accuracy on TRAIN + VAL + HOLDOUT | ≥ 50% each | 54% / 58% / 52% — **PASS** |
| E2 | Information Coefficient (IC 5d, Spearman) | > 0 on all three slices | +0.043 / +0.075 / +0.083 — **PASS** |
| E3 | Read coverage (frac non-FLAT days) | ≥ 30% (avoid perma-FLAT trivial ship) | 40% / 57% / 62% — **PASS** |
| E4 | Read stability | ≥ 70% (avoid churn) | 90% / 87% / 87% — **PASS** |
| E5 | Silent-live shadow window | ≥ 4 weeks in-envelope | 2/28 logged — **IN PROGRESS** |

These are ADDITIONAL, engine-only gates. They do not require
PROTOCOL amendment — PROTOCOL v0.1.0 is silent on read-level metrics,
so Owner can adopt them as an appendix or ship-decision guidance
without changing the numbered gates. Alternatively, publish this as
a new "PROTOCOL v0.1.1 — engine-only ship" mini-amendment.

## Ship sequence (if Owner picks this path)

1. Owner: opens SESSION3-REPORT.md, decides engine-only over v0.2.0.
2. Helios: writes `docs/PROTOCOL_v0.1.1_ENGINE_ONLY.md` codifying the
   E1-E5 gates and their thresholds.
3. Helios: shadow window continues (`scripts/shadow_log.py` daily).
   Reads-only shadow is the same log; only the interpretation changes.
4. On Gate E5 (shadow ≥ 4 weeks, in-envelope): ship weekly call as
   live. Daily brief stays shadow-only for now (does not clear IC on
   HOLDOUT at daily cadence — needs its own audit).
5. Package handoff pack per `docs/HANDOFF.md` MINUS the bot artifacts.
   Vega wires the "HELIOS says" panel.

## Trade-off

- **Pro:** Ships fast. Uses PROTOCOL v0.1.0 unchanged. Signal quality
  is honestly strong (all three IC > 0, all three WR-analog > 50%).
  Members get actionable oil view.
- **Con:** No on-chain agent — no trading revenue, no bot-mode member
  benefit. The bot line remains in R&D indefinitely (until Owner
  changes gates OR a new strategy family clears strict v0.1.0). AXIS
  ships a bot on BTC; Sable ships bots on gold; Helios not-shipping a
  bot on oil is asymmetric.
- **Path forward from here:** engine-only ship first; then reopen the
  bot conversation when we have (a) EIA-surprise feature that lifts
  VAL Sharpe, or (b) an alternative strategy family (e.g. mean-reversion
  on curve) that clears strict v0.1.0 on its own geometry.

## Decision matrix (for Owner)

| Decision | Bot | Engine | PROTOCOL change | Time-to-ship |
|---|---|---|---|---|
| Sign v0.2.0 | seed 7 ships after 4-wk shadow | seed 7 VoteConfig ships as signal | v0.1.0 → v0.2.0 | ~4 weeks |
| Reject v0.2.0, adopt engine-only | Deferred to R&D | seed 7 VoteConfig ships as signal | v0.1.0 unchanged + v0.1.1 appendix | ~4 weeks |
| Reject both | Deferred | Deferred | Unchanged | Blocked |

Recommendation: **sign v0.2.0** (SESSION3-REPORT.md primary rec).
Engine-only is Plan B if v0.2.0 has a policy-level objection.
