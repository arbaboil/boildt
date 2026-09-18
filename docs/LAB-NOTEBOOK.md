# HELIOS — Lab Notebook

Chronological record. Every meaningful run gets an entry.
Format per entry: date, intent, hypothesis, method, result one-liner, gate
pass/fail, artifacts, decisions.

---

## 2026-09-18 — Session 1 — Bootstrap

**Intent.** Stand up the Helios workspace per CLAUDE.md, seed docs, pull first
data, produce a working joined master parquet, and ship an engine v0 skeleton
end-to-end so downstream phases are unblocked.

**Method.** 
- git init, `.agent-name = helios`, folder tree
- Read FAR prior art (Argus BTC, AXIS, Sable) via Explore subagent, extract
  style guide
- Draft MISSION / ARCHITECTURE / DATA-SOURCES / PROTOCOL / RESEARCH-PLAN /
  REALISM / LAB-NOTEBOOK
- Wire `src/data/` pullers for FRED + Stooq + Yahoo + CFTC COT + Baker Hughes
- Wire `src/features/` deterministic feature matrix (subset of ARCHITECTURE
  targets — the ones that only need free daily data)
- Wire `src/engine/regime_vote.py` scaffold with hand-picked defaults
- Wire `src/sim/backtest.py` with locked cost model
- Wire `scripts/pull_data.py`, `scripts/build_features.py`,
  `scripts/backtest.py`, `scripts/walkforward.py`
- Run smoke backtest on 2001→2018 TRAIN slice
- Write unit tests for features, backtest, vintage safety

**Hypothesis.** Even a simple regime-vote model with trend + curve + COT
features should produce an above-random directional signal on weekly WTI,
because those three channels are known to carry information (curve backwardation
predicts spot strength, COT extremes predict reversals, long-term MA slope
captures trend regime).

**Result.**

Engine v0.1 (hand-picked defaults), weekly cadence, TRAIN 2001-2018:
- n=133 trades, WR 44.4%, mean R +0.27, total R +36.4
- Sharpe 0.59, bootstrap 95% CI [+0.009, +1.17] → PASSES gate 1 (CI>0)
- Directional WR 44.4% → FAILS gate 2 (≥50%)
- Permutation p=0.019 → PASSES gate 6

Walk-forward K=10 (2001-2023): 6/10 folds positive → FAILS 7/10 rule.
Fold 8 (2017-2019 shale glut) and fold 9 (2019-2021 COVID + negative WTI)
are the killers.

Bot GA v1 (median-Calmar fitness): overfit. Fired in only 2/5 folds with
12 trades total. Fitness +44 was gamed. Killed.

Bot GA v2 (worst-fold-Calmar + coverage gate) TRAIN 2006-2018 5-fold:
- Population 64, gens 30, sigma 0.12, seed 42
- Best fitness +6.056 (worst-fold Calmar after coverage penalty)
- 154 trades across ALL 5 folds, total R +169.8, max_dd 5.5R
- Fold Calmars: [6.06, 6.34, 8.49, 6.26, 7.83] — every fold positive

Bot v2 walk-forward K=10 (2006-2023):
- 10/10 folds positive expectancy → PASSES 7/10 rule
- 10/10 folds positive Sharpe
- Fold-by-fold WR 35-58%, mean-R +0.69 to +1.76 per fold

Bot v2 out-of-sample:
- TRAIN 2006-2018: n=153 WR 44% meanR +1.18 Sharpe 1.42 CI [+1.02, +1.81]
- VALIDATION 2019-2023: n=56 WR 43% meanR +0.98 Sharpe 1.24 CI [+0.43, +2.06]
- HOLDOUT 2024-present: n=27 WR 41% meanR +0.84 Sharpe 1.02 CI [-0.18, +1.85]

Evolved genome discovers a "cut losers small, let winners run" trend-follower:
- k_stop 0.78 ATR (tight), k_target 5.0 ATR (max)
- Max hold 7 days (short leash)
- Heaviest weights: macro (DXY) 4.0, momentum 3.8, trend 2.1
- Vol regime and COT positioning weights collapse to zero (ignored)
- Narrow strong-conviction band (moderate 0.17, strong 0.72)

**Gate pass/fail (Bot v2 seed 42).**

| # | Gate | TRAIN | VAL | HOLDOUT | Result |
|---|---|---|---|---|---|
| 1 | Sharpe CI > 0 | +1.02 | +0.43 | -0.18 | 2 of 3 slices PASS; HOLDOUT n=27 |
| 2 | Directional WR ≥ 50% | 44% | 43% | 41% | FAIL (asymmetric R:R strategy) |
| 3 | Min 100 trades in-sample | 153 | ✓ | ✓ | PASS |
| 4 | ≥ 7 of 10 folds positive | 10/10 | — | — | PASS |
| 5 | Max DD ≤ 15R | 5.5R | ✓ | ✓ | PASS |
| 6 | Permutation p ≤ 0.05 | pending re-run | | | pending |
| 7 | ≥ 4-week silent-live shadow | — | — | — | NOT STARTED |

Overall: fails Gate 2 (WR). Fails Gate 7 (shadow not started). Every other
gate passes on TRAIN + VAL.

**Artifacts.**
- `data/processed/oil_master.parquet` (28,103 rows, 21 cols, 1986-2026)
- `data/processed/features.parquet` (32 features)
- `results/backtests/engine_v0_train_{weekly,daily}.json`
- `results/walkforward/engine_v0_weekly_k10.json`
- `results/bots/bot_v1_seed42.json` (killed — overfit)
- `results/bots/bot_v2_seed42.json` (candidate)
- `results/bots/bot_v2_validation.json` (TRAIN/VAL/HOLDOUT slices)
- `results/walkforward/bot_v2_walkforward.json` (10/10 folds positive)
- `results/shadow/20260918.json` (first shadow entry, FLAT — coverage 36%)

**Decisions.**
- Weekly cadence primary, daily secondary. Daily gets `shadow_only` if it
  can't clear the same bar.
- Cost model 10 bps effective / 20 bps required edge — sits above FAR gold
  precedent, safer for physical-crude realities.
- HOLDOUT frozen at 2024-01-01 → present. Never touched during iteration.
- Bot v2 is a real candidate. WR gate (50%) blocks ship because the
  strategy is asymmetric-R:R (43% WR × 2.5:1 R:R = +1R expectancy).
  Options for owner: (a) escalate WR gate discussion / adopt expectancy-CI
  gate instead, (b) search v3 for a genome closer to 50% WR, (c) ship v2
  under an explicit disclosure.
- Bot v1 killed as overfit. Reason recorded in `feedback_helios_overfit_lesson_2026-09-18.md`.
- Shadow window NOT started. Not shipping anything until ≥4-week clean.

**Next session TODO.**
1. Run fresh-seed retest of bot v2 (20 unseen seeds; gate B7 in PROTOCOL)
2. Run bot v3 with a WR-weighted fitness variant to try to lift WR to 50%
3. Register EIA API key; add EIA weekly surprise feature; may lift WR
4. Wire `scripts/shadow_log.py` to a nightly cron; begin 4-week window
5. Draft owner-facing memo on WR gate for asymmetric R:R strategies

---
