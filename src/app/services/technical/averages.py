"""Moving averages."""

from collections.abc import Sequence

import numpy as np

from app.services.technical.common import (
    Series,
    as_series,
    as_volumes,
    pad,
    require_length,
    require_period,
    seeded_ema,
    windows,
)


def _prices(prices: Sequence[float], period: int, name: str) -> np.ndarray:
    require_period(period)
    data = as_series(prices, "prices", positive=True)
    require_length(data.size, period, f"{name}({period})")
    return data


def sma(prices: Sequence[float], period: int) -> Series:
    """SMA_t = (P_(t−N+1) + … + P_t) / N."""
    data = _prices(prices, period, "SMA")
    return pad(windows(data, period).mean(axis=1), data.size)


def ema(prices: Sequence[float], period: int) -> Series:
    """EMA_t = α P_t + (1 − α) EMA_(t−1), α = 2 / (N + 1), seeded with SMA of the first N."""
    data = _prices(prices, period, "EMA")
    return pad(seeded_ema(data, period, 2 / (period + 1)), data.size)


def wma(prices: Sequence[float], period: int) -> Series:
    """WMA_t = Σ_(i=1..N) i × P_(t−N+i) / (N (N + 1) / 2); the latest price has weight N."""
    data = _prices(prices, period, "WMA")
    weights = np.arange(1, period + 1, dtype=np.float64)
    return pad(windows(data, period) @ weights / weights.sum(), data.size)


def vwma(prices: Sequence[float], volumes: Sequence[float], period: int) -> Series:
    """VWMA_t = Σ P×V / Σ V over the window; None when the window volume is zero."""
    data = _prices(prices, period, "VWMA")
    volume = as_volumes(volumes, data.size)
    numerator = windows(data * volume, period).sum(axis=1)
    denominator = windows(volume, period).sum(axis=1)
    values = [None if v == 0 else float(n / v) for n, v in zip(numerator, denominator, strict=True)]
    return pad(values, data.size)
