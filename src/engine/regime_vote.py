"""HELIOS v0.1 regime-vote engine.

Each feature group votes +1 bullish / -1 bearish / 0 neutral. Weighted sum
maps to a read: STRONG_BUY / BUY / FLAT / SELL / STRONG_SELL.

Design principles (from FAR playbook):
- FLAT is a first-class output. Never force a signal that doesn't exist.
- Missing votes count as 0, not as a fill-in.
- Weights + thresholds are hand-picked from priors; tuning happens ONLY on
  TRAIN slice per PROTOCOL.md.
- Confidence = |weighted sum| normalized by max possible, additionally
  penalized by fraction of missing votes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class VoteConfig:
    # Group weights (sum matters; scale is arbitrary)
    w_trend: float = 3.0
    w_momentum: float = 2.0
    w_vol: float = 1.0
    w_curve: float = 2.0
    w_cot: float = 2.0
    w_eia: float = 2.0
    w_macro: float = 2.0

    # Trend thresholds (EMA slope in $/day)
    trend_bull: float = 0.02
    trend_bear: float = -0.02
    # Momentum (20d log-return)
    momo_bull: float = 0.03
    momo_bear: float = -0.03
    # Vol regime (VIX z-score)
    vol_hot: float = 1.0
    vol_cold: float = -1.0
    # Curve / crack spread (z-score)
    curve_bull: float = 0.75
    curve_bear: float = -0.75
    # COT managed-money net z-score (contrarian at extremes)
    cot_bull: float = -1.25  # extreme short = bullish reversal
    cot_bear: float = 1.5    # extreme long = bearish reversal
    # EIA weekly stocks surprise (positive surprise = bearish)
    eia_bear: float = 3000.0   # kb (thousand barrels)
    eia_bull: float = -3000.0
    # Macro (DXY 20d return; USD up = oil bearish)
    dxy_bear: float = 0.02
    dxy_bull: float = -0.02

    # Final discretization thresholds (weighted score / max_weight)
    strong: float = 0.60
    moderate: float = 0.20

    # Minimum vote coverage (fraction of non-NaN groups); below → FLAT
    min_coverage: float = 0.5


READS = ["STRONG_SELL", "SELL", "FLAT", "BUY", "STRONG_BUY"]


def _vote(x: float, bull: float, bear: float, invert: bool = False) -> int:
    if pd.isna(x):
        return 0
    if invert:
        # x above `bear` = bearish; below `bull` = bullish (used for DXY, COT extremes handled separately)
        if x >= bear:
            return -1
        if x <= bull:
            return +1
        return 0
    if x >= bull:
        return +1
    if x <= bear:
        return -1
    return 0


def _cot_vote(z: float, bull_extreme: float, bear_extreme: float) -> int:
    if pd.isna(z):
        return 0
    # Contrarian: extreme short position (very negative) → bullish
    if z <= bull_extreme:
        return +1
    if z >= bear_extreme:
        return -1
    return 0


def _vol_vote(z: float, hot: float, cold: float) -> int:
    """Vol vote: hot vol = bearish (crashes cluster in high-vol); cold vol = mildly bullish."""
    if pd.isna(z):
        return 0
    if z >= hot:
        return -1
    if z <= cold:
        return +1
    return 0


def score_row(row: pd.Series, cfg: VoteConfig) -> dict[str, Any]:
    votes: dict[str, int] = {}
    weights: dict[str, float] = {}
    have: dict[str, bool] = {}

    # Trend (EMA200 slope + EMA50 slope both must agree for a strong vote;
    # we simplify: use EMA50 slope as the trend axis and let momentum handle
    # short-term push)
    slope50 = row.get("wti_ema50_slope", np.nan)
    votes["trend"] = _vote(slope50, cfg.trend_bull, cfg.trend_bear)
    weights["trend"] = cfg.w_trend
    have["trend"] = not pd.isna(slope50)

    # Momentum: 20d log-return
    ret20 = row.get("wti_ret_20d", np.nan)
    votes["momentum"] = _vote(ret20, cfg.momo_bull, cfg.momo_bear)
    weights["momentum"] = cfg.w_momentum
    have["momentum"] = not pd.isna(ret20)

    # Vol regime
    vixz = row.get("vix_z156w", np.nan)
    votes["vol"] = _vol_vote(vixz, cfg.vol_hot, cfg.vol_cold)
    weights["vol"] = cfg.w_vol
    have["vol"] = not pd.isna(vixz)

    # Curve / crack spread
    crackz = row.get("crack_spread_z", np.nan)
    votes["curve"] = _vote(crackz, cfg.curve_bull, cfg.curve_bear)
    weights["curve"] = cfg.w_curve
    have["curve"] = not pd.isna(crackz)

    # COT positioning (contrarian at extremes)
    cotz = row.get("cot_mm_net_wti_z", np.nan)
    votes["cot"] = _cot_vote(cotz, cfg.cot_bull, cfg.cot_bear)
    weights["cot"] = cfg.w_cot
    have["cot"] = not pd.isna(cotz)

    # EIA weekly surprise (positive surprise = bearish)
    eias = row.get("eia_stocks_surprise", np.nan)
    votes["eia"] = _vote(eias, cfg.eia_bull, cfg.eia_bear, invert=True) if pd.notna(eias) else 0
    weights["eia"] = cfg.w_eia
    have["eia"] = not pd.isna(eias)

    # Macro: DXY 20d return (USD up = oil bearish → invert axis)
    dxyr = row.get("dxy_ret_20d", np.nan)
    votes["macro"] = _vote(dxyr, cfg.dxy_bull, cfg.dxy_bear, invert=True) if pd.notna(dxyr) else 0
    weights["macro"] = cfg.w_macro
    have["macro"] = not pd.isna(dxyr)

    # Weighted score
    max_w = sum(weights[g] for g in weights)
    active_w = sum(weights[g] for g in weights if have[g])
    if max_w == 0:
        return {"read": "FLAT", "score": 0.0, "confidence": 0.0,
                "coverage": 0.0, "votes": votes}
    weighted = sum(votes[g] * weights[g] for g in votes if have[g])
    score = weighted / max_w
    coverage = active_w / max_w

    if coverage < cfg.min_coverage:
        read = "FLAT"
    elif score >= cfg.strong:
        read = "STRONG_BUY"
    elif score >= cfg.moderate:
        read = "BUY"
    elif score <= -cfg.strong:
        read = "STRONG_SELL"
    elif score <= -cfg.moderate:
        read = "SELL"
    else:
        read = "FLAT"

    # Confidence: absolute score scaled by coverage (missing votes lower it)
    confidence = float(min(1.0, abs(score) / max(cfg.moderate, 1e-6))) * coverage
    confidence = float(min(1.0, confidence))

    return {"read": read, "score": float(score), "confidence": confidence,
            "coverage": float(coverage), "votes": votes}


def _ternary(x: np.ndarray, bull: float, bear: float,
             invert: bool = False) -> np.ndarray:
    """Vectorized ternary vote (missing → 0)."""
    v = np.zeros(len(x), dtype=np.int8)
    m = ~np.isnan(x)
    if invert:
        v[m & (x <= bull)] = 1
        v[m & (x >= bear)] = -1
    else:
        v[m & (x >= bull)] = 1
        v[m & (x <= bear)] = -1
    return v


def _cot_vec(z: np.ndarray, bull_ext: float, bear_ext: float) -> np.ndarray:
    v = np.zeros(len(z), dtype=np.int8)
    m = ~np.isnan(z)
    v[m & (z <= bull_ext)] = 1
    v[m & (z >= bear_ext)] = -1
    return v


def _vol_vec(z: np.ndarray, hot: float, cold: float) -> np.ndarray:
    v = np.zeros(len(z), dtype=np.int8)
    m = ~np.isnan(z)
    v[m & (z >= hot)] = -1
    v[m & (z <= cold)] = 1
    return v


def score_matrix(features: pd.DataFrame,
                 cfg: VoteConfig | None = None) -> pd.DataFrame:
    """Vectorized regime-vote scoring across the whole feature matrix."""
    cfg = cfg or VoteConfig()
    n = len(features)

    def col(name: str) -> np.ndarray:
        if name in features:
            return features[name].to_numpy(dtype=float)
        return np.full(n, np.nan)

    slope50 = col("wti_ema50_slope")
    ret20 = col("wti_ret_20d")
    vixz = col("vix_z156w")
    crackz = col("crack_spread_z")
    cotz = col("cot_mm_net_wti_z")
    eias = col("eia_stocks_surprise")
    dxyr = col("dxy_ret_20d")

    v_trend = _ternary(slope50, cfg.trend_bull, cfg.trend_bear)
    v_momo = _ternary(ret20, cfg.momo_bull, cfg.momo_bear)
    v_vol = _vol_vec(vixz, cfg.vol_hot, cfg.vol_cold)
    v_curve = _ternary(crackz, cfg.curve_bull, cfg.curve_bear)
    v_cot = _cot_vec(cotz, cfg.cot_bull, cfg.cot_bear)
    v_eia = _ternary(eias, cfg.eia_bull, cfg.eia_bear, invert=True)
    v_macro = _ternary(dxyr, cfg.dxy_bull, cfg.dxy_bear, invert=True)

    have_trend = ~np.isnan(slope50)
    have_momo = ~np.isnan(ret20)
    have_vol = ~np.isnan(vixz)
    have_curve = ~np.isnan(crackz)
    have_cot = ~np.isnan(cotz)
    have_eia = ~np.isnan(eias)
    have_macro = ~np.isnan(dxyr)

    weights = np.array([cfg.w_trend, cfg.w_momentum, cfg.w_vol, cfg.w_curve,
                        cfg.w_cot, cfg.w_eia, cfg.w_macro], dtype=float)
    max_w = weights.sum()

    haves = np.stack([have_trend, have_momo, have_vol, have_curve,
                      have_cot, have_eia, have_macro], axis=0).astype(float)
    votes = np.stack([v_trend, v_momo, v_vol, v_curve,
                      v_cot, v_eia, v_macro], axis=0).astype(float)

    active_w = (haves * weights[:, None]).sum(axis=0)
    weighted = (votes * haves * weights[:, None]).sum(axis=0)
    score = np.where(max_w > 0, weighted / max_w, 0.0)
    coverage = np.where(max_w > 0, active_w / max_w, 0.0)

    read = np.full(n, "FLAT", dtype=object)
    dir_ok = coverage >= cfg.min_coverage
    read[dir_ok & (score >= cfg.strong)] = "STRONG_BUY"
    read[dir_ok & (score >= cfg.moderate) & (score < cfg.strong)] = "BUY"
    read[dir_ok & (score <= -cfg.strong)] = "STRONG_SELL"
    read[dir_ok & (score <= -cfg.moderate) & (score > -cfg.strong)] = "SELL"

    denom = max(cfg.moderate, 1e-6)
    confidence = np.minimum(1.0, np.abs(score) / denom) * coverage
    confidence = np.minimum(1.0, confidence)

    return pd.DataFrame({
        "date": features["date"].to_numpy(),
        "read": read,
        "score": score,
        "confidence": confidence,
        "coverage": coverage,
        "vote_trend": v_trend,
        "vote_momentum": v_momo,
        "vote_vol": v_vol,
        "vote_curve": v_curve,
        "vote_cot": v_cot,
        "vote_eia": v_eia,
        "vote_macro": v_macro,
    })


READ_TO_SIGN = {
    "STRONG_BUY": 2,
    "BUY": 1,
    "FLAT": 0,
    "SELL": -1,
    "STRONG_SELL": -2,
}


def read_to_sign(read: str) -> int:
    return READ_TO_SIGN.get(read, 0)
