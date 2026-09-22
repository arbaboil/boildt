---
name: EIA API key stored in .env (session 3, 2026-09-22)
description: Owner provided EIA v2 API key. Stored in .env under EIA_API_KEY. Free key, unlimited hourly rate for weekly data.
type: reference
---

**Where the key lives.** `.env` at repo root, key `EIA_API_KEY`. `.env` is gitignored (see `.gitignore` line 37). Read via `src/util/config.py::get_key("EIA_API_KEY")`. `src/data/eia.py::pull_eia()` uses it automatically.

**Coverage.** Weekly petroleum status data 1982-08-20 → present. 5 series pulled: `us_crude_stocks_kb`, `us_refinery_input_kbd`, `us_refinery_util_pct`, `us_crude_imports_kbd`, `us_crude_exports_kbd`. Landed in features as `eia_crude_stocks_wchg` (weekly change), `eia_stocks_surprise` (deviation from 5y seasonal median), `eia_refutil_z` (z-scored refinery util).

**How to refresh.** `python -c "from src.data.eia import pull_eia; pull_eia()"` — one call. Or `scripts/pull_data.py` (default runs all sources including EIA if key present).

**How to apply.** After first EIA pull the master + features must be rebuilt (`build_master` + `scripts/build_features.py`). Then any candidate audit / emit re-uses the new features automatically. Seed 7 audit re-run showed TRAIN Sharpe +1.60 → +1.75 and VAL Sharpe +1.24 → +1.36 with EIA; HOLDOUT Sharpe +1.49 → +1.11 (small regression, 54-trade slice noisy). All v0.2.0 gates still pass on all 3 slices.

**Rotation.** If Owner rotates the key, update the `EIA_API_KEY=` line in `.env`. No git changes needed (file is gitignored).
