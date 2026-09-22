---
name: ATR (and rolling indicators) must ffill through market holidays
description: build_features must forward-fill price series before rolling indicators — one NaN kills 20+ days of ATR
type: feedback
---

Every rolling indicator with `min_periods=window` (ATR, slope, RV, MACD,
donchian, zscore) fails on any window that contains a NaN. The master
parquet is on a business-day calendar; US market holidays land as NaN
closes, so ~10 holidays/year × 20-day windows means most windows contain a
NaN → ATR is valid ~34% of the time. Since `backtest.py` gates on
`pd.notna(atr20)`, this silently drops ~66% of tradeable opportunities.

**Why:** Session 2 (2026-09-22) discovered Session 1's engine v0 backtest
had 133 trades in TRAIN 2001-2018 when correct-data count is 361 (nearly
3× more). Fix committed in `96696fb`.

**How to apply.** In `src/features/build.py`, forward-fill the underlying
price series (wti, brent, vix, ovx, ho, rb, dxy, sp500, etc.) before
computing indicators. Preserve the raw `wti_close` in the output so the
backtest still gates on market-open days. Test coverage:
`tests/test_build_features_gaps.py` — three regression tests including a
`test_train_slice_atr_fully_populated` that asserts no NaNs in real 2002+
TRAIN slice ATR.

**Also**: `build_features()` used to always write to disk. That means any
test calling it with synthetic data clobbered the real features parquet.
Fixed by making `write` default to `True` only when `master=None` (real
data path). Pass a master in tests and the write is suppressed.
