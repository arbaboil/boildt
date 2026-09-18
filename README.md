# HELIOS — Oil Intelligence Engine

Named for the Greek sun god because oil is the world's stored solar energy.

Standalone R&D workspace for the FAR Action Radar oil vertical.
Weekly + daily reads on WTI + Brent, plus a genetically-trained trading bot.

**Status:** scaffolding + skeleton engine in place. Data pulls stubbed;
production ship gates in `docs/PROTOCOL.md` (locked).

## Quickstart

```bash
python -m venv .venv
. .venv/Scripts/activate            # Windows Git Bash
pip install -r requirements.txt

# fill in .env from .env.example (FRED_API_KEY, EIA_API_KEY, NOAA_TOKEN)
cp .env.example .env

# 1. Pull data (idempotent; safe to rerun)
python scripts/pull_data.py --full

# 2. Build feature matrix
python scripts/build_features.py

# 3. Smoke backtest of engine v0
python scripts/backtest.py --engine v0 --slice train

# 4. Walk-forward K-fold
python scripts/walkforward.py --engine v0 --folds 10

# 5. Tests
pytest -q
```

## Layout

```
docs/       — MISSION, ARCHITECTURE, DATA-SOURCES, PROTOCOL, RESEARCH-PLAN,
              REALISM, LAB-NOTEBOOK
src/        — data, features, engine, bot, sim, util
scripts/    — pull_data, build_features, backtest, walkforward, evolve_bot,
              shadow_log
results/    — backtests, walkforward, monte_carlo, shadow (regenerated)
data/       — raw pulls (parquet), processed master
tests/      — pytest suite
handoff/    — ship-ready pack for Vega (site integration)
memory/     — auto-memory index
```

## Ship gates (see docs/PROTOCOL.md for the full spec)

Weekly engine ships when:
- Sharpe block-bootstrap 95% CI lower bound > 0
- Directional WR (excl FLAT) ≥ 50%
- Min 100 in-sample trades
- ≥ 7 of 10 walk-forward folds positive
- Permutation-test p ≤ 0.05
- ≥ 4-week silent-live shadow in-envelope

Daily brief ships under the same bar or is marked `shadow_only=true`.

Bot ships under the additional bar of held-out Calmar ≥ 1.0, DD < 40%, net
edge ≥ 20 bps, Sortino 95% CI > 0.5, regime-consistent, and fresh-seed retest.

## Isolation rule

Helios does not edit anything under `C:\dev\FarACtionRadar\v16build\`.
Ship = drop into `handoff/`, notify owner, owner relays to Vega.
Agent: helios
