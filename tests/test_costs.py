"""Cost model tests."""
from __future__ import annotations

import math

from src.sim.costs import CostModel


def test_default_baseline():
    c = CostModel()
    assert c.roundtrip_bps(atr_pct=0.02, atr_median_pct=0.02) == 10.0


def test_vol_scaling_high_vol():
    c = CostModel()
    # ATR doubled → +5 bps
    bps = c.roundtrip_bps(atr_pct=0.04, atr_median_pct=0.02)
    assert math.isclose(bps, 15.0, abs_tol=1e-6)


def test_low_vol_stays_baseline():
    c = CostModel()
    # ATR below median → no discount, but no penalty either
    bps = c.roundtrip_bps(atr_pct=0.01, atr_median_pct=0.02)
    assert bps == 10.0


def test_nan_inputs_return_base():
    c = CostModel()
    import math
    assert c.roundtrip_bps(atr_pct=math.nan, atr_median_pct=0.02) == 10.0
    assert c.roundtrip_bps(atr_pct=0.02, atr_median_pct=math.nan) == 10.0
