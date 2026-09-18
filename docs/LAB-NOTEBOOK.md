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

**Result.** [populated after runs land]

**Gate pass/fail.** [populated after gate checks]

**Artifacts.**
- `docs/*.md` (drafted this session)
- `data/processed/oil_master_YYYYMMDD.parquet` (pending pull)
- `results/backtests/engine_v0_smoke.json` (pending)

**Decisions.**
- Weekly cadence primary, daily secondary. Daily gets `shadow_only` if it
  can't clear the same bar.
- Cost model 10 bps effective / 20 bps required edge — sits above FAR gold
  precedent, safer for physical-crude realities.
- HOLDOUT frozen at 2024-01-01 → present. Never touched during iteration.

---
