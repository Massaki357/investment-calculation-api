"""Volatility indicators."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.exceptions import InvalidInputError
from app.services.technical.common import (
    Series,
    as_ohlc,
    as_series,
    pad,
    require_length,
    require_period,
    rolling_reduce,
    seeded_ema,
    windows,
)


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """TR_t = max(H_t − L_t, |H_t − C_(t−1)|, |L_t − C_(t−1)|) for t ≥ 1."""
    previous = close[:-1]
    return np.maximum.reduce(
        [high[1:] - low[1:], np.abs(high[1:] - previous), np.abs(low[1:] - previous)]
    )


def atr(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
) -> Series:
    """Wilder ATR.

    First ATR = mean(TR_1..TR_N) at t = N; then ATR_t = (ATR_(t−1) × (N − 1) + TR_t) / N.
    """
    require_period(period)
    bar = as_ohlc(high, low, close)
    require_length(bar.close.size, period + 1, f"ATR({period})")
    ranges = true_range(bar.high, bar.low, bar.close)
    return pad(seeded_ema(ranges, period, 1 / period), bar.close.size)


@dataclass(frozen=True, slots=True)
class Bollinger:
    middle: Series
    upper: Series
    lower: Series
    percent_b: Series
    bandwidth: Series


def bollinger_bands(
    prices: Sequence[float], period: int = 20, standard_deviations: float = 2.0
) -> Bollinger:
    """middle = SMA_N; upper/lower = middle ± k × σ_N (population σ);
    %B = (P − lower) / (upper − lower); bandwidth = (upper − lower) / middle."""
    require_period(period)
    if standard_deviations <= 0:
        raise InvalidInputError("standard_deviations must be greater than zero")
    data = as_series(prices, "prices", positive=True)
    require_length(data.size, period, f"Bollinger Bands({period})")
    middle = windows(data, period).mean(axis=1)
    sigma = rolling_reduce(data, period, lambda rows: rows.std(axis=1, ddof=0))
    upper = middle + standard_deviations * sigma
    lower = middle - standard_deviations * sigma
    width = upper - lower
    latest = data[period - 1 :]
    percent_b = [
        None if w == 0 else float((p - lo) / w)
        for p, lo, w in zip(latest, lower, width, strict=True)
    ]
    return Bollinger(
        middle=pad(middle, data.size),
        upper=pad(upper, data.size),
        lower=pad(lower, data.size),
        percent_b=pad(percent_b, data.size),
        bandwidth=pad(width / middle, data.size),
    )


def historical_volatility(
    prices: Sequence[float], period: int = 20, periods_per_year: int = 252
) -> Series:
    """HV_t = sample σ of the last N log returns × √periods_per_year (first value at t = N)."""
    if period < 2:
        raise InvalidInputError("period must be at least 2 for a sample standard deviation")
    data = as_series(prices, "prices", positive=True)
    require_length(data.size, period + 1, f"Historical Volatility({period})")
    log_returns = np.log(data[1:] / data[:-1])
    sigma = rolling_reduce(log_returns, period, lambda rows: rows.std(axis=1, ddof=1))
    return pad(sigma * math.sqrt(periods_per_year), data.size)
