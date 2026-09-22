# HELIOS — Data Sources

**Rule: free-only unless owner authorizes paid.**
Each source below is public / free-key / no-key. When a feature demands a paid
API, surface the ask; never silently drop.

Every puller lives under `src/data/` and writes parquet to
`data/raw/{source}_{asset}.parquet`. The daily-frequency master is joined into
`data/processed/oil_master_{YYYYMMDD}.parquet`.

Time zone: everything stored in UTC. Session labels derived at feature time.
Publication delays are enforced in feature construction, not at data pull.

---

## Price & fundamentals

### EIA v2 API — the single most important oil source
- Endpoint: `https://api.eia.gov/v2/`
- Key: free, register at eia.gov. Store in `.env` as `EIA_API_KEY`.
- Rate limit: 5,000 requests/hour anonymous; 10,000 with key.
- Datasets used:
  - `petroleum/stoc/wstk/data/` — weekly crude/gasoline/distillate stocks
  - `petroleum/pnp/wiup/data/` — refinery input & utilization
  - `petroleum/move/wkly/data/` — imports/exports weekly
  - `petroleum/pri/spt/data/` — spot prices (WTI Cushing, Brent, gasoline)
  - `petroleum/crd/drill/data/` — active rigs (also cross-checked vs. Baker Hughes)
- Frequency: weekly, released Wednesdays 10:30 ET (`4 business day delay`
  for backtest purposes to be safe).
- Historical depth: back to 1982 for weekly stocks, longer for spot prices.

### FRED
- Endpoint: `https://api.stlouisfed.org/fred/series/observations`
- Key: owner already has one (`4180f00923aa22abe2f07d3bc01634c7`); store in
  `.env` as `FRED_API_KEY`.
- Rate limit: 120 req/min.
- Series used:
  - `DCOILWTICO` — WTI daily spot (back to 1986)
  - `DCOILBRENTEU` — Brent daily spot (back to 1987)
  - `DTWEXBGS` — trade-weighted USD (broad)
  - `DFII10` — 10y real yield (TIPS-derived)
  - `VIXCLS` — VIX close
  - `INDPRO` — industrial production (monthly)
  - `NAPMPI` / `MANEMP` proxies for ISM
  - `T10Y3M` — yield curve slope
- Frequency: daily (most), monthly for macro series.
- Historical depth: 30–40 yrs typical.

### Yahoo Finance
- Endpoint: `https://query1.finance.yahoo.com/v7/finance/download/{ticker}`
- Key: none (public).
- Rate limit: soft; use `time.sleep(0.5)` between calls.
- Tickers:
  - `CL=F` — WTI continuous front-month (back to ~2000 reliably)
  - `BZ=F` — Brent continuous front-month
  - `OVX` — Cboe crude-oil volatility index
  - `DX-Y.NYB` — DXY daily
- Frequency: daily.

### Stooq
- Endpoint: `https://stooq.com/q/d/l/?s={symbol}&d1={YYYYMMDD}&d2={YYYYMMDD}&i=d`
- Key: none.
- Rate limit: 5–10 req/sec courteous.
- Symbols:
  - `cl.f` — WTI daily (back to 1983)
  - `cb.f` — Brent daily (back to 1988)
  - `xoi.us` — NYSE Arca Oil Index
- Used for pre-2000 history where Yahoo is thin.

### OPEC Monthly Oil Market Report (MOMR)
- Endpoint: PDF archive at `https://www.opec.org/opec_web/en/publications/202.htm`
  plus `archive.org` mirrors.
- Key: none. Text extraction via `pdfplumber`.
- Frequency: monthly, second week of the month.
- Fields extracted: OPEC crude production by country, total supply,
  compliance vs. quota, world oil demand forecast, spare capacity estimate.
- Historical depth: back to 2001 easily; older via archive.org.

### Baker Hughes rig count
- Endpoint: `https://rigcount.bakerhughes.com/rig-count-overview` (CSV export
  link on page) plus historical Excel at
  `https://rigcount.bakerhughes.com/na-rig-count`
- Key: none.
- Frequency: weekly, released Fridays.
- Coverage: US oil rigs, Canada oil rigs, international quarterly.
- Historical depth: US back to 1944.

---

## Positioning & flows

### CFTC Commitment of Traders (COT)
- Endpoint: `https://www.cftc.gov/dea/newcot/deacot{YYYY}.txt` (or `.zip` for
  full history disaggregated).
- Key: none.
- Frequency: weekly, Fridays 3:30 ET, reflecting Tuesday snapshot.
- Fields used: managed money net long, net short, spread positions; producer
  hedging net short; open interest total.
- Contracts: `067651` (Light Sweet Crude WTI), `06765T` (Brent LTD).
- Historical depth: disaggregated back to 2006; legacy weekly back to 1986.

### ICE Brent open interest
- Endpoint: `https://www.theice.com/marketdata/reports/8` (daily OI CSV).
- Key: none.
- Frequency: daily.
- Used as sanity check on Brent-specific positioning.

---

## Geopolitics, weather, event risk

### GDELT 2.0
- Endpoint: `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` (rolling
  15-minute event feed).
- Key: none.
- Rate limit: generous, be polite.
- Filter: CAMEO event codes 18-20 (violence) + `oil` / `refinery` / `pipeline`
  / `sanction` keyword hit in URL or title. Countries of interest:
  SAU, IRN, RUS, USA, VEN, IRQ, LBY, NGA, MEX.
- Output: daily count of oil-relevant events, z-score against 156w rolling
  history.

### Wikipedia oil-crisis timeline
- Source: hand-curated JSON in `data/raw/geo_events_manual.json`, seeded
  from Wikipedia articles: 1973 crisis, 1979 crisis, 1990 Gulf War, 2003
  Iraq, 2008 spike, 2014 crash, 2020 negative WTI, Ukraine 2022, etc.
- Purpose: label training data for regime detection; also feeds world-sim.

### NOAA (weather demand-side)
- Endpoint: `https://www.ncei.noaa.gov/access/services/data/v1` (GHCND)
- Key: free registration, `NOAA_TOKEN`.
- Series: HDD/CDD anomalies aggregated to US Census regions (weighted by
  heating-oil consumption share).
- Frequency: daily.

### NHC hurricane tracks
- Endpoint: `https://www.nhc.noaa.gov/data/hurdat/`
- Key: none.
- Purpose: binary Gulf-of-Mexico hurricane-active flag for refinery/rig
  disruption risk.

---

## Explicitly OFF-LIMITS unless owner authorizes

- Bloomberg Terminal
- Refinitiv / LSEG
- Kpler (satellite-derived crude-in-transit; would be gold, but paid)
- OilX
- S&P Platts assessments
- Any paid Xignite / Quandl-premium

If a feature is materially better with paid data, **surface the trade-off in
`LAB-NOTEBOOK.md`** and wait for owner call.

---

## Cache & refresh policy

- Full historical pull on first run (single command
  `python scripts/pull_data.py --full`).
- Incremental pull daily via `python scripts/pull_data.py --incremental`.
- Each puller records its last-successful-timestamp in
  `data/raw/_meta.json` for idempotent restarts.
- If a source is unreachable, log and continue — never let one down source
  block the whole pull. Feature layer handles missing values explicitly
  (never silently zero-fill).

## Vintages & look-ahead prevention

Every feature function accepts `as_of: date`. Feature construction uses
`data[data.publish_date <= as_of]`, NOT `data[data.observation_date <= as_of]`.
- EIA weekly: publish_date = observation_date + 4 business days
- COT: publish_date = observation_date + 3 business days
- OPEC monthly: publish_date = observation_date + ~14 days
- FRED daily series (spot prices, DXY, yields): publish_date = observation_date
- FRED monthly (INDPRO, ISM): publish_date = observation_date + ~15 days

`src/features/vintage.py` centralizes these delays; every feature calls
`safe_asof(source, as_of)` before slicing.
