# Daily-cadence v0.3.0 scope — research memo

Status: RESEARCH ONLY (no code changes). Draft date: 2026-10-12.

## Why this memo

Weekly bot v3 seed 7 is LIVE under PROTOCOL v0.2.1. Daily brief remains
`shadow_only=true` in `results/emitted/daily/current.json`. The site shows
the daily read but no capital rides it. Members have been asking "when does
daily go live?". This memo scopes the fix.

## Blocker analysis

Running bot v3 seed 7 genome forced to `daily_cadence=True`, three slices:

| Slice | n | WR | mean R | Sharpe CI | max_dd | perm p | g5 (DD≤15R) |
|---|---|---|---|---|---|---|---|
| TRAIN 2006-2018 | 359 | 32% | +0.81 | [+0.95, +1.89] | **18.4R** | 0.000 | ✗ |
| VAL 2019-2023 | 129 | 34% | +1.08 | [+0.81, +2.63] | 11.4R | 0.000 | ✓ |
| HOLDOUT 2024→ | 81 | 33% | +0.68 | [+0.37, +2.11] | 11.7R | 0.011 | ✓ |

Gates 1, 2a, 2b, 3, 4, 6 all pass. Only **Gate 5 on TRAIN** fails.

## Where the DD comes from

TRAIN max-DD trough is **2013-09-17** after a decline from a 2013-03-04 peak.
A six-month 2013 chop killed 18.4R of equity across ~30 trades. Yearly DD
breakdown:

```
2006:  5.69R    2010:  8.77R    2014:  5.03R
2007:  6.57R    2011:  7.14R    2015:  9.68R
2008:  5.42R    2012: 12.33R    2016:  5.25R
2009:  8.38R    2013: 18.40R <  2017:  5.78R
                                 2018:  5.57R
```

This is **not** a crisis event: 2008 financial crisis = 5.4R DD; 2014 oil
crash = 5.0R DD; 2020 COVID (in VAL) = 11.4R DD worst-case. The failure is
chop-regime noise accumulation, not tail risk.

The daily cadence fires ~2.8x more trades than weekly (359 vs ~128 on same
window). Expected: chop periods accumulate losses faster when fire rate is
higher.

## Candidate fixes (ranked by expected impact + implementation cost)

### Option A — chop-regime filter (recommended)

Add a vote filter: do not fire when `atr20_pct` is below its trailing 252d
25th percentile (quiet-market gate). The 2013 chop period had ATR_pct
compressed below the long-run median, so this filter would skip ~40% of
2013 entries.

- Cost: ~1 day. Adds one indicator + one filter row in `score_matrix`.
- Risk: may also skip high-expectancy quiet-market signals; must re-check
  VAL + HOLDOUT after.
- Testable via existing `daily_cadence` sweep infrastructure.

### Option B — post-stop cool-off

After any STOP outcome, skip the next 3-5 trading days before accepting a
new entry. 2013 chop had ~8 consecutive STOP sequences; cool-off would
cut DD contribution substantially.

- Cost: ~0.5 day. Trade logic change in `src/sim/backtest.py` + genome
  parameter.
- Risk: adds a new GA dimension (cool-off window length). Re-evolve required
  or hard-code a defensible value from a small grid.

### Option C — daily-specific genome re-evolve

Re-run the GA with `daily_cadence=True` fixed and the DD gate hard in
fitness. The current genome was selected under weekly fitness; it's
plausible a daily-native genome exists in the search space.

- Cost: 2-3 days (one GA run = ~15 min × 20 seeds = ~5 hours wall; add
  ablation + Monte Carlo).
- Risk: no new mechanism, so the DD/trade-count tradeoff may just reproduce
  the same chop problem at a different point. Need A or B stacked with it.

### Option D — equity-drawdown position-sizing

Cut position size by half when rolling 60d equity-R is below −8R. Classic
circuit-breaker. Would cap the 2013 DD at ~12R mechanically.

- Cost: ~1 day. New sim state (equity tracker) + genome parameter.
- Risk: distorts R-accounting (position size no longer ≡ 1R stop). Needs a
  new metrics convention; downstream artifact schemas (daily-brief.json)
  would need a `size_multiplier` field.

## Recommended path

Stack **A + B**: chop filter + 3-day cool-off, no genome re-evolve, no
sizing change. These two mechanisms directly address the chop-noise failure
mode. Target: cut TRAIN max_dd ≤ 12R while preserving VAL + HOLDOUT edge.

If A + B alone don't clear Gate 5, add **C** (re-evolve with daily-native
fitness) — but only after A + B's mechanism effect is isolated.

**Not recommended:** Option D (sizing) until Gates 1-6 clear with A + B.
Changing R-geometry mid-protocol breaks comparability with weekly artifact
schemas, which Vega integrates into the site layout.

## Promotion criteria (v0.3.0 lock)

Daily brief flips to `shadow_only=false` only after a candidate genome under
daily cadence:

1. Clears all v0.2.0 gates on TRAIN + VAL + HOLDOUT (including Gate 5
   max_dd ≤ 15R on **all three** slices).
2. Completes a fresh 28-day Gate 7 shadow window **under daily cadence**.
3. Owner signs off per the same amendment-log pattern as v0.2.1.

No v0.3.0 override planned. The weekly bot's successful live monitoring is
the paved road; daily does the full window.

## Decision needed from Owner

Approve recommendation (A + B first, C fallback), or redirect. No code work
starts until that approval. Memo lives in `docs/DAILY-V03-SCOPE.md`.
