---
name: Helios workspace bootstrap 2026-09-18
description: First-session scaffold state for Helios — docs, data, engine, GA scaffold, tests
type: project
---

**Repo:** `C:\Users\farha\OneDrive\Desktop\oil\` (standalone R&D; NOT inside FAR site repo). `.agent-name = helios`. Git initialized on `main`.

**Docs shipped:** MISSION, ARCHITECTURE, DATA-SOURCES, PROTOCOL (v0.1.0 locked with time-slice split TRAIN 2001-2018 / VAL 2019-2023 / HOLDOUT 2024-present), RESEARCH-PLAN, REALISM (v0.1 score 37/100 with 80/100 roadmap), LAB-NOTEBOOK.

**Data:** `data/processed/oil_master.parquet` — 28,103 rows, 21 columns, WTI/Brent 1986→2026-09-18. FRED (WTI/Brent/DXY/real_yield_10y/VIX/YC/INDPRO/HY_OAS/nom_10y). Yahoo v8 chart (WTI/Brent/OVX/DXY/VIX/SP500/HO/RB/NG). CFTC SODA (WTI 817 weeks 2006+, Brent 240 weeks 2019+). Stooq behind JS challenge (parked). EIA (needs owner API key, deferred).

**Features:** 32 features across trend/momentum/vol/curve/COT/EIA/macro, deterministic, vectorized. No look-ahead by construction.

**Engine v0.1:** Regime-vote with 7 groups. Vectorized `score_matrix`. Weekly-cadence TRAIN 2001-2018 backtest: 133 trades, WR 44.4% (FAILS ≥50% gate), Sharpe 0.59 with 95% CI [+0.009, +1.17] (PASSES CI>0), permutation p=0.019 (PASSES), total +36R over 18 yrs. Daily cadence: Sharpe CI crosses zero → shadow-only.

**Walk-forward K=10 (2001-2023):** 6/10 folds positive expectancy. FAILS 7/10 gate. Folds 8 (2017-2019) + 9 (2019-2021 COVID) are the killers.

**Bot GA v1:** overfit — gamed median-Calmar by firing in only 2/5 folds. v2 (now running) uses worst-fold Calmar + `MIN_ACTIVE_FOLDS_FRAC=0.8` + `MIN_TRADES_TOTAL=30` gates.

**Tests:** 33 pytest cases green (indicators, regime_vote, backtest, vintage, costs, metrics, genome).

**Not shipped:** engine fails walk-forward gate. Bot GA running. Shadow window not started. Nothing member-visible.

**Why:** owner asked for a highest-quality replica of Argus (BTC) / Sable (gold) for oil. Ship-gate discipline is non-negotiable.

**How to apply:** next session, review the running GA v2 result. If GA converges to a stable ≥ 4-active-fold, positive-worst-fold-Calmar genome, re-run walk-forward on the tuned VoteConfig. Otherwise iterate on features (add EIA weekly surprise, add regime labels, add refinery-util). Do NOT ship until 7/10 K-fold gate and ≥4-week shadow are both green.

**Session-1 end state (2026-09-18 21:03 UTC).** Two commits on `main` (16cb2cb + 3823ac0). No remote yet — Owner to create GitHub repo. Working tree clean. 33 tests green. GA v2 done + validated + committed. Nothing ship-ready. Bot v2 passes 5/6 statistical gates including 10/10 K-fold, fails WR ≥50% gate (asymmetric R:R). Next-session TODO in `docs/LAB-NOTEBOOK.md`.
