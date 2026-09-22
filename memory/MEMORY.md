# Memory Index (Helios)

- [Helios workspace bootstrap 2026-09-18](project_helios_bootstrap_2026-09-18.md) — first session scaffold; docs + data + engine v0.1 + GA v1 landed; engine fails walk-forward 7/10 gate honestly; GA v2 with worst-fold Calmar gating in progress
- [Helios ship gates locked 2026-09-18](reference_helios_ship_gates.md) — pointer to docs/PROTOCOL.md v0.1.0 (weekly Sharpe CI>0, WR≥50%, ≥100 trades, ≥7/10 folds, 4-wk shadow; bot adds Calmar≥1.0, DD<40%, edge≥20bps, Sortino CI>0.5, regime-consistent, fresh-seed retest)
- [Helios data sources 2026-09-18](reference_helios_data_sources.md) — FRED + Yahoo v8 chart + CFTC SODA disaggregated + optional Stooq (JS challenge) + EIA v2 (needs key). Master parquet has 21 cols spanning 1986-2026
- [Helios overfit lesson 2026-09-18 — fitness must penalize inactive folds](feedback_helios_overfit_lesson_2026-09-18.md) — GA v1 gamed median-Calmar by firing in only 2/5 folds; v2 uses worst-fold Calmar + MIN_ACTIVE_FOLDS_FRAC=0.8 + MIN_TRADES_TOTAL=30
- [Helios bot v2 candidate 2026-09-18](project_helios_bot_v2_2026-09-18.md) — GA-tuned genome passes 10/10 K-fold, +0.84R HOLDOUT expectancy, but 43% WR fails 50% gate; asymmetric-R:R trend follower on DXY+momentum+trend (superseded by ATR fix — see session 2)
- [ATR ffill required through holidays](feedback_atr_ffill_indicators.md) — build_features must forward-fill price series or holiday NaN wipes rolling indicators. Session 1 backtests were on ~34% of real trade universe.
- [Helios bot v3 candidate — seed 7](project_helios_bot_v3_2026-09-22.md) — post-fix winner from 20-seed sweep; Sharpe CI>0 on TRAIN+VAL+HOLDOUT; WF 10/10; blocked only by 50% WR gate (structural — 0/20 seeds pass WR).
- [WR gate structurally unreachable for oil](feedback_wr_gate_structural_2026-09-22.md) — 20 independent GA seeds all converge to R:R 4-7 asymmetric strategies. Memo recommends Option B (expectancy-CI replacement).
