---
name: Argus (BTC) soft-ships signals-only 2026-10-20 — autotrader deferred
description: Cross-vertical context from Vega's 2026-10-12 message. Argus shadow failed (W1 RED → W2 AMBER → W3 AMBER, −14.34% vs BTC-hold, chart-only genome). Helios RIG remains the only autotrader cutover candidate.
type: project
---

**Owner decision (per Vega relay 2026-10-12).** Argus BTC bot
soft-ships 2026-10-20 as signals-only. Autotrader cutover deferred
indefinitely.

**Argus shadow failure pattern:**
- W1 shadow colour: RED
- W2 → W3: AMBER (progressively failing)
- Realized return: −14.34% vs BTC-hold baseline
- Diagnosis: "chart-only-genome" — strategy relied solely on chart
  indicators (price/MA/volume), no fundamentals
- Retune experiment ruled out rescue (couldn't fix via GA retune)

**Implications for Helios (RIG):**
- 10-20 is Helios's own autotrader-cutover expectation per Vega
  (but see `memory/project_helios_vega_schema_convention_mirrored_2026-10-12.md`
  for the Gate 7 date discrepancy — 10-20 is pre-outage math; actual
  Gate 7 completes ~2026-11-04).
- Helios will not be a joint ship with Argus on autotrader; Helios
  stands alone on the autotrader side.
- Argus's failure pattern (chart-only genome, no fundamental votes)
  is explicitly NOT the Helios design — our 7 vote components span
  price (trend/momentum/vol), curve (crack spread), positioning
  (COT), supply/demand (EIA), and macro (DXY). Multi-source signal
  resilience is a design goal, now validated as the correct call by
  Argus's negative evidence.
- Candidate seed 7's HOLDOUT mean R +0.73 + Monte Carlo
  P(final>0, 1yr) = 99.2% / P(ruin) = 0% is the counterfactual to
  Argus's −14.34% drawdown. If anything, the Argus outcome
  strengthens the case for Helios's current protocol discipline.

**Not an action item.** Pure context for ship-day coordination.
No reply to Vega needed — the message was informational.
