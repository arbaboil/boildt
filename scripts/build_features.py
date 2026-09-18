"""Build the feature matrix from the joined oil_master parquet."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.build import build_features


def main() -> int:
    f = build_features()
    print(f"Features: rows={len(f):,} cols={len(f.columns)}")
    n_nn = f.dropna().shape[0]
    print(f"Fully-populated rows (all features present): {n_nn:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
