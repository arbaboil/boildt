"""Locked cost model per docs/PROTOCOL.md."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 5.0          # roundtrip commission
    slippage_bps: float = 5.0            # baseline slippage
    slippage_vol_multiplier: float = 5.0  # +bps per ATR doubling above 20d median
    roll_dollars_per_barrel: float = 0.10  # $/bbl every 21 trading days
    roll_frequency_days: int = 21

    def roundtrip_bps(self, atr_pct: float, atr_median_pct: float) -> float:
        """Return the total roundtrip cost in bps.

        Slippage scales with ATR ratio (relative to trailing median):
        each doubling above median adds `slippage_vol_multiplier` bps.
        """
        base = self.commission_bps + self.slippage_bps
        if atr_pct is None or atr_median_pct is None:
            return base
        if atr_median_pct <= 0 or np.isnan(atr_pct) or np.isnan(atr_median_pct):
            return base
        doublings = max(0.0, np.log2(atr_pct / atr_median_pct))
        return base + self.slippage_vol_multiplier * doublings
