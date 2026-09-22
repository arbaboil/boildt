---
name: Helios session 2 extended state (2026-09-22)
description: Post-fix state after fresh-seed sweep, Gate 6, regime labels, Monte Carlo, DATA-CONTRACT, and deploy pack
type: project
---

**End-of-session state (2026-09-22 ~09:30 UTC).** 11 commits on `main`. 53 tests green. No git remote yet.

**Bot v3 seed 7 candidate.** `results/bots/bot_v3_seed7_candidate.json`. Automated gate audit (`results/bots/bot_v3_seed7_candidate_audit.json`):
- G1 Sharpe CI > 0: PASS on all three slices (TRAIN +1.14, VAL +0.43, HOLDOUT +0.61)
- G2 WR >= 50%: FAIL on all (38 / 33 / 36) — same for all 20 sweep seeds; structural to oil
- G3 n >= 100: PASS (238 on TRAIN)
- G4 WF K=10: PASS (10/10 positive-expectancy folds)
- G5 max_dd <= 15R: PASS on all (10.7 / 10.2 / 6.8)
- G6 permutation p <= 0.05: PASS on all (0.000 / 0.003 / 0.008)
- B6 regime consistency: PASS (bull mean_R +0.86, chop +1.58, bear +1.11 combined TRAIN+VAL)
- G7 shadow window: NOT STARTED (blocked pending PROTOCOL v0.2.0 sign-off)

**Monte Carlo.** `results/monte_carlo/bot_v3_seed7_candidate_mc.json`. 10k paths of 40 trades (~1 year weekly). Baseline: 98.9% positive year, median +41.6R, 95th-percentile drawdown 13.5R, 0.00% ruin probability. Under +5 bps stress: 98.5% positive, 0.00% ruin. Very robust.

**Site integration pack.** `docs/DATA-CONTRACT.md` locks schemas for `weekly/current.json`, `daily/current.json`, `history/index.json`, `backtest/summary.json` (modeled on AXIS emit.ts). `scripts/emit_reads.py` produces contract-compliant JSON; kill-switch and priceStep bounds implemented and unit-tested. `docs/HANDOFF.md` + `docs/DEPLOY-PLAN.md` describe what Vega needs.

**Daily cadence status.** Post-ATR-fix, daily engine passes Sharpe CI (was FAIL in session 1). Bot v3 forced-daily variant: Sharpe CI positive on all slices, permutation p<0.02, but TRAIN max_dd 18.4R fails Gate 5. Weekly stays the ship variant; daily brief is `shadow_only=true`.

**Ship-readiness snapshot.**
- Data infra: 85%
- Features: 75%
- Engine v0.1: 60% (walk-forward passes, still lacks strict Sharpe CI clearance with hand-picked defaults)
- Daily brief: 30%
- Bot line (v3 seed 7): 85%
- Ship gates + protocol discipline: 95%
- Site integration prep: 60%
- **Overall: ~60% ready**

**Blocked on Owner (in priority order):**
1. Sign or reject `docs/PROTOCOL_v0.2.0_DRAFT.md` (expectancy-CI replacement for WR gate). Unblocks bot ship path.
2. EIA API key for weekly petroleum status feed. Enables real consensus-vs-actual surprise feature.
3. Approval to hand pack to Vega (Helios doesn't talk to other agents).
4. GitHub remote for repo push (still no remote configured; commits are local-only).

**How to apply.** Next session: assume Owner is ready to make the PROTOCOL call. If approved, launch shadow window via `python scripts/shadow_log.py --candidate results/bots/bot_v3_seed7_candidate.json` daily for 4 weeks; monitor drift against WF envelope. If EIA key provided, wire the feature and re-run the fresh-seed sweep to see if it lifts VAL or HOLDOUT metrics. Also consider engine-only VoteConfig tuning (fix TradeConfig to symmetric 1.5/3.0 R:R) as a v0.1.0-passable variant if Owner wants a shippable engine before the bot decision.
