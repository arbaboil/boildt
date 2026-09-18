"""Deterministic indicator computations.

All functions take a Series indexed by date and return a Series aligned to
the input index. No RNG, no time.now(). No look-ahead: every rolling window
ends at or before the label date; use `shift(1)` at consumer level when
strictly forward-looking is required.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def ema(x: pd.Series, span: int) -> pd.Series:
    return x.ewm(span=span, adjust=False, min_periods=span).mean()


def sma(x: pd.Series, window: int) -> pd.Series:
    return x.rolling(window=window, min_periods=window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    au = up.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    ad = down.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def atr_from_close(close: pd.Series, window: int = 20) -> pd.Series:
    """Cash-series ATR proxy (no OHLC available): abs day-over-day change."""
    ret = close.diff().abs()
    return ret.rolling(window=window, min_periods=window).mean()


def zscore(x: pd.Series, window: int) -> pd.Series:
    mu = x.rolling(window=window, min_periods=window).mean()
    sd = x.rolling(window=window, min_periods=window).std(ddof=0)
    return (x - mu) / sd.replace(0, np.nan)


def slope(x: pd.Series, window: int) -> pd.Series:
    """Least-squares slope over a rolling window, in units-per-day."""
    def _s(y: np.ndarray) -> float:
        n = len(y)
        if np.isnan(y).any() or n < 2:
            return np.nan
        t = np.arange(n)
        t_mean = t.mean()
        y_mean = y.mean()
        num = ((t - t_mean) * (y - y_mean)).sum()
        den = ((t - t_mean) ** 2).sum()
        return num / den if den != 0 else np.nan
    return x.rolling(window=window, min_periods=window).apply(_s, raw=True)


def donchian_position(close: pd.Series, window: int = 55) -> pd.Series:
    hi = close.rolling(window=window, min_periods=window).max()
    lo = close.rolling(window=window, min_periods=window).min()
    return (close - lo) / (hi - lo).replace(0, np.nan)


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    r = log_returns(close)
    return r.rolling(window=window, min_periods=window).std(ddof=0) * np.sqrt(252)


def macd_hist(close: pd.Series, fast: int = 12, slow: int = 26,
              signal: int = 9) -> pd.Series:
    e1 = ema(close, fast)
    e2 = ema(close, slow)
    line = e1 - e2
    sig = ema(line, signal)
    return line - sig
