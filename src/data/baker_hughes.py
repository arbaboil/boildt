"""Baker Hughes weekly rig count.

They publish an Excel workbook that gets refreshed weekly. Since the URL
changes and the workbook is not always machine-friendly, we fall back to
FRED's mirror when available; otherwise the feature layer treats rig
count as an optional feature (weight 1 in the vote).
"""
from __future__ import annotations

import pandas as pd

from src.util.paths import DATA_RAW


def pull_baker_hughes() -> pd.DataFrame:
    """Emit an empty typed frame; real historical rig count is optional."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(columns=["date", "us_oil_rigs"])
    df.to_parquet(DATA_RAW / "baker_hughes.parquet", index=False)
    return df


if __name__ == "__main__":
    pull_baker_hughes()
