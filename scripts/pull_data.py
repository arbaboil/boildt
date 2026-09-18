"""One-shot data pull.

Usage:
    python scripts/pull_data.py                # everything
    python scripts/pull_data.py --skip eia cot # skip EIA and COT
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.util.paths import ensure_dirs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[],
                    choices=["fred", "stooq", "yahoo", "cot", "eia", "baker"])
    args = ap.parse_args()

    ensure_dirs()

    steps = [
        ("stooq", "src.data.stooq", "pull_stooq"),
        ("fred", "src.data.fred", "pull_fred"),
        ("yahoo", "src.data.yahoo", "pull_yahoo"),
        ("cot", "src.data.cot", "pull_cot"),
        ("eia", "src.data.eia", "pull_eia"),
        ("baker", "src.data.baker_hughes", "pull_baker_hughes"),
    ]

    for name, module, fn in steps:
        if name in args.skip:
            print(f"[skip] {name}")
            continue
        print(f"[pull] {name}")
        try:
            mod = __import__(module, fromlist=[fn])
            getattr(mod, fn)()
        except Exception as e:  # network/keys may fail; keep going
            print(f"[warn] {name} failed: {e}")
            traceback.print_exc()

    # Master join
    print("[join] master")
    from src.data.master import build_master
    df = build_master()
    print(f"       rows={len(df):,} cols={len(df.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
