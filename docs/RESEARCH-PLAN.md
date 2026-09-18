# HELIOS — Research Plan

Phased. Each phase gates on data-honesty, not calendar. No dates promised.

## Phase 0 — Bootstrap (this session)

- git init, folder structure, `.agent-name = helios`
- Draft MISSION, ARCHITECTURE, DATA-SOURCES, RESEARCH-PLAN, PROTOCOL, REALISM
- Scaffold memory index
- Write first pull scripts (Stooq + FRED + Yahoo) and confirm end-to-end
  data lands in parquet.

Exit: `data/processed/oil_master_YYYYMMDD.parquet` produced with WTI + Brent
+ DXY + real yields + VIX and ≥30 years of daily rows.

## Phase 1 — Full data pull

- EIA v2 weekly stocks + refinery util + imports/exports (needs API key)
- CFTC COT WTI + Brent disaggregated (back to 2006)
- OPEC MOMR archive (best-effort PDF parse; skip years that fail with a note)
- Baker Hughes weekly rig count
- GDELT oil-event daily count
- NOAA HDD/CDD (US regional heating anomaly)
- NHC Gulf-hurricane flag

Exit: `data/processed/oil_master.parquet` joined at daily frequency with all
sources present, coverage report written to `docs/DATA-COVERAGE.md`.

## Phase 2 — Feature engineering

- Deterministic feature layer with `as_of` vintage safety
- ~40 features across 8 groups (see ARCHITECTURE.md)
- Sanity smoke test: replay historical dates, confirm no look-ahead
- Unit tests on each feature (`tests/test_features.py`)

Exit: feature matrix reproducible byte-for-byte across two runs from same
data snapshot.

## Phase 3 — Engine v1 (weekly)

- Regime-vote model with hand-picked thresholds from Phase 2 EDA
- Backtest 2001→present on weekly bars (Sunday 22:00 UTC close analog)
- Report: Sharpe + block-bootstrap 95% CI, directional-WR (excl FLAT),
  FLAT-rate, expectancy in R, max DD, Calmar
- Baseline against buy-and-hold and against random-vote null
- If Sharpe CI lower bound > 0 and WR ≥ 50% and ≥ 100 trades, proceed

Exit: `results/backtests/engine_v1_weekly.json` + summary in LAB-NOTEBOOK.

## Phase 4 — Engine v2 (daily brief)

- Same feature matrix, daily bars, tighter conviction thresholds
- Backtest with daily rebalance; report same metrics
- If daily cannot clear the same gates as weekly, keep daily but mark
  `shadow_only=true` in the output schema. No forcing.

Exit: either daily gates pass → publishable both, or daily shadow-only.

## Phase 5 — Walk-forward K-fold + overfit audit

- 10 folds, chronological, non-overlapping test windows
- Fixed 8-year sliding train; last 4 folds cover post-2016 volatility regime
- Success = ≥ 7 of 10 folds positive-expectancy AND overall bootstrap CI
  lower bound > 0
- Permutation test: shuffle signal-day alignment 1,000×, verify observed
  metric is > 95th percentile of shuffled distribution
- If a fold catastrophically fails, do a regime post-mortem before iterating

Exit: `results/walkforward/engine_v1.json` with fold-by-fold results and
permutation p-value.

## Phase 6 — Shadow window (≥ 4 weeks silent-live)

- Wire `scripts/shadow_log.py` to run daily at cron: pull latest data, run
  engine, append output + market snapshot to `results/shadow/YYYYMMDD.json`
- Do NOT publish to members
- After 4 weeks: measure shadow-vs-backtest divergence. If shadow WR /
  expectancy inside walk-forward fold envelope, cleared for owner review.

Exit: 4-week shadow log clean and inside envelope.

## Phase 7 — Bot v1 (world-sim + genetic training)

- Build `src/sim/world.py` daily-tick environment with intrabar fills,
  ATR-geometry stops, locked cost model, event overlay
- Build `src/bot/genome.py` with ~24 genes as in ARCHITECTURE.md
- Run GA for a small population (32) for a fast sanity iteration
- Compare best genome vs. engine's regime-vote read on the same fold: if
  bot beats engine on Calmar AND passes gates, keep exploring; otherwise
  investigate why (maybe engine is the truth and bot is chasing)

Exit: `results/bots/v1_smoke.json` with best genome + fitness distribution.

## Phase 8 — Bot v2 (full evolutionary run + Monte Carlo)

- Population 128, elitism 8, tournament-3, uniform crossover, Gaussian
  mutation σ=0.10 × gene-range
- Fitness = geometric mean of Calmar across walk-forward folds × survival
- 10,000-path Monte Carlo bootstrap on trade sequence for drawdown envelope
- Held-out validation on 2024→present (dates never used during training)
- Honest overfit audit: fresh random seeds (never seen), report metrics
  independently; if held-out CI includes total loss under realistic slippage,
  do not ship.

Exit: `results/bots/v2_evolved.json` with full audit trail.

## Phase 9 — Handoff pack

- `handoff/weekly-call.schema.json`, `handoff/daily-brief.schema.json`
- `handoff/engine_bundle/` (Python module with a single entrypoint)
- `handoff/bot/genome.json`, `handoff/bot/replay.py`, `handoff/bot/README.md`
- `handoff/README-vega.md` — one-page integration guide, kill-switch spec,
  deploy checklist, cost-model disclosure, shadow-log summary

Exit: owner satisfied, ready to relay to Vega.

## Discipline

- **No promised dates.** Owner sets pace.
- **Commit + push after each phase.** Owner has been burned by lost work.
- **Update `LAB-NOTEBOOK.md`** with intent / hypothesis / result / gate
  pass-fail after every meaningful run.
- **Update `memory/`** at session end.
- **When in doubt: STOP AND ASK.** Never fake a number to unblock a phase.
