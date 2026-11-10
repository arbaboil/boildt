"""Owner 2026-11-10: confidence-outlier sigma floored at 10 points."""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dm", REPO / "scripts" / "drift_monitor.py")
dm = importlib.util.module_from_spec(spec); spec.loader.exec_module(dm)

# Baseline like the live one: median 92, tiny sigma. Last entry = today (excluded).
HIST = [{"confidence": c} for c in [0.92, 0.90, 0.95, 0.92, 0.89, 0.92, 0.94, 0.92, 0.0]]


def test_small_move_no_longer_trips():
    assert dm.check_confidence_outlier({"confidence": 75}, HIST) == []   # |d|=17 < 20


def test_large_move_still_trips():
    assert dm.check_confidence_outlier({"confidence": 69}, HIST)          # |d|=23
    assert dm.check_confidence_outlier({"confidence": 22}, HIST)


def test_constant_baseline_now_checked():
    flat = [{"confidence": 0.92}] * 6
    assert dm.check_confidence_outlier({"confidence": 92}, flat) == []
    assert dm.check_confidence_outlier({"confidence": 50}, flat)
