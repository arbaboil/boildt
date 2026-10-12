# HELIOS v2 — feature-expansion research memo

Status: RESEARCH + ONE SILENT-BUG FIX LANDED. Draft 2026-10-12.

Scope: identify the next edge candidates after bot v3 seed 7 goes live.
Owner's framing: "once the current bot proves out in shadow, what should
we try next?"

## Finding 0 — silent COT WTI data bug (fixed in this session)

Investigating v2 features surfaced a current-live-model data bug worth
flagging first.

**Bug.** The CFTC SODA puller (`src/data/cot.py`) looked up WTI by the
market-name `CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE`.
CFTC renamed that contract to `WTI-PHYSICAL - NEW YORK MERCANTILE
EXCHANGE` after the 2022-02-01 report. The contract market code (067651)
was preserved. The puller silently returned zero rows after the rename
and `cot_mm_net_wti` has been NaN since 2022-02 — including the entire
HOLDOUT (2024→present) and the live shadow window.

**Impact assessment.** Live model's `vote_cot = 0` in all 10 shadow
entries 2026-09-18 → 2026-10-09. Re-ran candidate audit with corrected
COT data over 2001-2026:

| Slice | Pre-fix n/R | Post-fix n/R | g1-g6 |
|---|---|---|---|
| TRAIN     | 234 / +1.29 | 234 / +1.29 | pass |
| VAL       | 95  / +0.92 | 97  / +0.98 | pass |
| HOLDOUT   | 54  / +0.73 | 58  / +0.73 | pass |

Four extra HOLDOUT trades at +0.73 R each — essentially the model's
holdout expectancy, confirming the cot vote is modest but not harmful.
Live behavior change would be ~1-2 extra signals per quarter.

**Fix.** Query SODA by `cftc_contract_market_code` (stable across
renames) instead of market name. Verified pulls restore 2022-2026
coverage: WTI now 1061 rows through 2026-10-06.

**Deploy decision.** Fix is committed but needs Owner awareness before
auto-propagating to the live cron. The next cron run will use the fixed
data and the model's cot vote will begin firing per the genome
(`w_cot=0.98`, `cot_bull=-0.64`, `cot_bear=+2.5` — contrarian). Owner
should decide whether to:
  (a) Let the fix roll — low-risk per audit, drift monitor is the safety net
  (b) Pin a `cot_disabled` flag until a formal data-contract bump
  (c) Pause live, re-audit holistically, then re-enable
Recommend (a). The audit shows this change is strictly in-envelope.

## Finding 1 — Baker Hughes rig count stub

`src/data/baker_hughes.py` is intentionally an empty-frame stub. FRED
mirrors a few proxies that could backfill:

- `IPG211111CS` — Oil & Gas Extraction Industrial Production, monthly
- `OILFORECAST*` series — EIA short-term outlook

Rig count historically leads WTI with 8-12 week lag (CapEx response).
Low-urgency feature; backlog item not v2 blocker.

## v2 feature candidates — hypothesis + feasibility

### Candidate A — COT managed-money depth features

With cot_wti now flowing, the current genome only uses `cot_mm_net_z`.
Deeper features worth testing:

- `cot_mm_net_delta_4w`: 4-week change in net positioning (acceleration)
- `cot_mm_net_percentile_156w`: 3-yr percentile rank (extreme regime)
- `cot_mm_long_short_ratio_z`: long vs short imbalance Z
- `cot_prod_net_delta_4w`: producer hedging acceleration
- `cot_divergence`: `cot_mm_net_z - price_momentum_z` (positioning vs
  price divergence — classic sentiment indicator)

Hypothesis: managed-money *acceleration* and *extremes* carry more
signal than level. Verifiable via drop-in grid search over existing
engine.

Feasibility: ✓ free, already in COT pull.

### Candidate B — OPEC monthly compliance

Monthly OPEC MOMR (Oil Market Report) publishes production quotas +
actual production per member. Compliance = quota minus actual, averaged
across members. Compliance spikes historically coincide with
coordinated supply shocks.

- Source: OPEC MOMR PDF (table 11 — "World oil supply"), monthly.
  Mirror on archive.org. Published around the 10th-15th of each month.
- Feature: `opec_compliance_12m_z` (12-month rolling Z of compliance %)
- Vintage lag: ~2 weeks post-month-end.
- Signal lag: supply shocks move price with 1-4 week delay.

Hypothesis: compliance regime shifts predict multi-week WTI drifts.
2020 collapse, 2022 Russian cut-off, 2023 Saudi voluntary cuts all
coincided with compliance regime changes.

Feasibility: ⚠ PDF scrape required; brittle. Alternative is Yahoo-style
proxy via `OPEC Reference Basket` price feed if free.

### Candidate C — EIA weekly surprise features (expand existing)

Current `eia_stocks_surprise` only uses crude stocks delta vs consensus.
Expand to:

- `eia_distillate_surprise`: distillate stocks vs 4w avg
- `eia_gasoline_surprise`: gasoline stocks vs 4w avg
- `eia_crack_margin`: computed crack spread as a demand proxy
- `eia_refutil_delta`: refinery utilization 4w change

Hypothesis: distillate + gasoline surprises carry demand-side info
that crude stocks alone miss (crude builds can be bullish if refiners
run hot).

Feasibility: ✓ EIA API wired, add fields in `src/data/eia.py`.

### Candidate D — Geopolitical event scoring (GDELT)

Free global event database with daily event counts tagged by actor +
location + CAMEO code. Oil-relevant filters: Middle East location
+ "Military Action" or "Sanctions" CAMEO codes.

- Source: GDELT `v2.gdeltproject.org` — bulk CSV, daily refresh.
- Feature: `gdelt_oil_event_z` = 7d rolling event count Z-score, filtered
  to oil-producing regions.
- Vintage lag: 24h.

Hypothesis: GDELT event-count spikes 24-48h ahead of oil-price moves on
geopolitical catalysts (strait closures, pipeline attacks, OPEC
emergency meetings).

Feasibility: ✓ free, Python client exists. ~1 day integration.
Risk: noisy; needs careful feature engineering.

### Candidate E — Hurricane risk (NOAA / NHC)

Already in DATA-SOURCES.md. US Gulf of Mexico produces ~15% of US crude;
hurricane shutdowns cause ~2-5% stock delta spikes. Seasonal — only
Jun-Nov relevant. NHC publishes 5-day cone forecasts; feature:
`gom_hurricane_risk` = max probability of Cat-1+ landfall in US
Gulf region.

Feasibility: ⚠ seasonal + rare events. Low Sharpe-per-trade contribution
but potentially high R-per-trade when triggered.

## Recommended v2 roadmap

**Phase 2a (next 2 weeks post-ship):** Candidate A (COT depth) + C
(EIA expansion). Both expand existing data pulls, drop-in feature
tests. GA re-sweep with expanded feature matrix; promote any genome
that improves VAL Sharpe CI without widening HOLDOUT DD.

**Phase 2b (month 2):** Candidate D (GDELT). Needs infrastructure. If
tests show no edge, drop and move on.

**Phase 2c (opportunistic):** Candidates B + E. PDF scraping and
seasonal signals are higher-cost per expected-benefit. Only if 2a
and 2b produce an upgrade worth defending.

**Hold until next cycle:** Baker Hughes integration (low priority).

## Protocol stance

Any v2 genome ship still runs:
- All v0.2.0 gates on TRAIN + VAL + HOLDOUT
- Fresh 28-day Gate 7 shadow (no override planned)
- A/B comparison vs. live bot v3 seed 7 — v2 must dominate on at least
  mean R or Sharpe CI, not just WR

v0.2.1's early-ship override was a one-time concession based on evidence
weight; subsequent ships use the paved road.

## Decision needed from Owner

1. Approve the silent-cot-fix for live deployment (recommendation: yes).
2. Approve the Phase 2a scope (COT depth + EIA expansion) as the next
   research initiative post-ship.
3. Defer phases 2b/c/baker-hughes to backlog.

Memo lives at `docs/V2-FEATURE-RESEARCH.md`.
