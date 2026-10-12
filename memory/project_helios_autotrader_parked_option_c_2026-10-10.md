---
name: Oil autotrader parked at option C (signal-only) 2026-10-10 — review gate 2026-11-08
description: Owner directive 2026-10-10 parks the on-chain executor; 10-20 ships RIG as signals-only parallel to Argus. Autotrader re-opens for review only after a post-ship signals audit clears post-2026-11-08.
type: project
---

**Owner directive, relayed via Vega 2026-10-12:**

Per owner directive 2026-10-10, the oil (RIG/Helios) autotrader is
**parked at option C — signals-only**. No on-chain execution venue
picked. No router contract deployed. No executor worker written. The
"Autotrader" column in the /access Oil tab is a UI placeholder, not a
live executor.

**Ship-day semantics for 2026-10-20:**
- Helios ships as a **signals-only engine**.
- Parallel to Argus's own soft-ship signals-only decision from the
  same week (see `memory/project_argus_soft_ship_2026-10-20.md`).
- Signals already render live on /oil (Vega commit 9e76dc0, 2026-10-12).
- Gate 7 shadow-window formally completes ~2026-11-04 (independent
  of the signals-only cutover).

**Autotrader review gate:**
- Oil autotrader re-opens for owner review **only after 2026-11-08**.
- Opens **only if** RIG clears its post-ship signals audit (post-10-20).
- Any autotrader-schema changes (signal_id, position_sizing_hint,
  payload fields the executor would need) are on a **schema-v2
  wishlist** — not 10-20 scope.

**Why:** Prudent soft-ship pattern given Argus's shadow failure
(W1 RED → W2/W3 AMBER, −14.34% vs BTC-hold, chart-only genome).
Owner wants two signals ships behaving in live render before any
on-chain capital rides on either engine.

**How to apply.** When planning work:
- Treat 10-20 as a signals cutover, not an autotrader cutover. Any
  work scoped around "ship-day autotrader prep" is premature.
- Keep the signal-emission pipeline stable + clean through 10-20
  and the following signals audit window.
- Do NOT add autotrader-adjacent payload fields (signal_id,
  position_sizing_hint, early_close_rule) to current payload. All
  three deferred to schema-v2 if/when autotrader opens.
- Shadow_audit.json schema is now a stability promise — Vega may
  consume read-only for a v1.1 /oil tile. If I change its shape,
  ping Vega with the "Vega validator update required" header.
- 2026-11-08 is the next event horizon worth planning around.
  Design a post-ship signals-audit plan ahead of that gate.

**Replaces earlier framing:** My 2026-10-12 memo
`docs/memos/2026-10-12_autotrader_cutover_readiness.md` was written
under the assumption that 10-20 was an autotrader cutover. The audit
findings (payload surface, kill-switch, bounds, ship prerequisites)
are still correct for the signals-only cutover; only the framing was
wrong. See amendment at the bottom of that memo.
