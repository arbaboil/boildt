---
name: Helios session 3 state (2026-09-22)
description: End-of-session-3 state — WR-pressure sweep closed the WR-vs-Sharpe-CI question; ship-readiness dashboard + SESSION3-REPORT delivered; bot ship still owner-blocked on PROTOCOL v0.2.0 sign-off
type: project
---

**End-of-session state (2026-09-22 UTC, session 3).** Extends session 2. Working-tree changes ready to commit; scripts + tests + docs added; no new remote.

**What landed this session:**
- `scripts/wr_pressure_sweep.py` executed 10 seeds (21-30) → `results/wr_pressure/seed_02*.json` + `results/bots/wr_pressure_sweep.json`. Verdict: 10/10 pass WR on TRAIN, 8/10 pass WR on VAL, but **0/10 pass Sharpe CI-low > 0 on VAL** (all -0.16 to -0.76).
- `results/bots/engine_v02_sweep.json` + `results/engine_v02/seed_*.json` committed (from session 2 continuation): 12-seed engine-only tuning with locked symmetric R:R (1.5/3.0). All fail Gate 1 CI on VAL/HOLDOUT — locked symmetric R:R destroys generalization.
- `scripts/ship_readiness.py` + `tests/test_ship_readiness.py` (15 tests) — single dashboard aggregating candidate audit + cost stress + drift + Monte Carlo + shadow log + all three sweeps into a green/red verdict for Owner.
- `docs/SESSION3-REPORT.md` — consolidated evidence report for PROTOCOL v0.2.0 sign-off decision.

**Definitive finding:** Across three orthogonal GA search strategies covering 42 candidate seeds, **zero** seeds pass both Gate 1 (Sharpe CI-low > 0 on VAL) AND Gate 2 (WR ≥ 50% on VAL). The gates are in structural tension for oil's signal manifold. PROTOCOL v0.2.0 is not "the easier path" — it is the *only* path that admits any ship candidate at all. See `memory/feedback_wr_gate_structural_2026-09-22.md`.

**Ship-readiness (post session 3):**
- Data infra: 85%
- Features: 75%
- Engine v0.1: 65% (VoteConfig locked to seed 7 shape via emitter; engine ships reads not trades)
- Daily brief: 30% (shadow-only unchanged)
- Bot line (v3 seed 7): 90% (all evidence consolidated; ready for shadow window continuation)
- Ship gates + protocol discipline: 95%
- Site integration prep: 65% (dashboard adds machine-readable verdict)
- **Overall: ~68% ready**

**Owner-blocked (in priority order):**
1. Sign or reject `docs/PROTOCOL_v0.2.0_DRAFT.md` — the SESSION3-REPORT is the artifact to review before signing.
2. EIA API key (features could lift VAL/HO metrics).
3. GitHub remote push.
4. Vega handoff clearance.

**Test count:** 53 → 68 tests (15 new `test_ship_readiness.py` tests). All green.

**How to apply next session.** If Owner signs v0.2.0: bump PROTOCOL, continue Gate 7 shadow (26 days remaining as of 2026-09-22), package handoff pack for Vega. If Owner rejects: reconsider engine-only ship using seed 7 VoteConfig without the bot layer (engine emits reads; trading logic reserved for later). Either way, `scripts/ship_readiness.py` is the single source of truth for ship-decision status — rerun after any new artifact lands.
