---
name: Helios data sources
description: Working free sources + gotchas (Yahoo v8 chart, Stooq JS challenge, CFTC SODA market names)
type: reference
---

Full details in `docs/DATA-SOURCES.md`. Gotchas learned this session:

- **Yahoo Finance:** legacy `/v7/finance/download` endpoint returns 401 as of 2024. Use `/v8/finance/chart` with a browser User-Agent. Puller at `src/data/yahoo.py`. Tickers pulled: CL=F, BZ=F, ^OVX, DX-Y.NYB, ^VIX, ^GSPC, HO=F, RB=F, NG=F.
- **Stooq:** now serves a JS challenge on `cl.f` / `cb.f` — treat as best-effort only. Fallback to FRED spot + Yahoo futures.
- **CFTC SODA:** market names have spaces around the dash. `"CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE"` (not `-NYMEX`). `"BRENT LAST DAY - NEW YORK MERCANTILE EXCHANGE"`.
- **FRED:** owner's key = `4180f00923aa22abe2f07d3bc01634c7`, stored in `.env` as `FRED_API_KEY`. `NAPMPI` is a dead series (400); use `MANEMP` for manufacturing employment.
- **EIA v2:** needs owner-created key (free at eia.gov/opendata). Not pulled this session. Puller wired at `src/data/eia.py`.
- **Master parquet:** `data/processed/oil_master.parquet` — 21 columns, 28k business-day rows.

**How to apply:** if a puller returns 0 rows, first check the endpoint's current state (curl -I) before assuming code bug. Endpoints move.
