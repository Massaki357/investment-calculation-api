"""Shared helpers for indicator series."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.core.exceptions import InsufficientDataError, InvalidInputError
from app.services.statistics.descriptive import FloatArray

Series = list[float | None]


def as_series(values: Sequence[float], name: str, *, positive: bool = False) -> FloatArray:
    data = np.asarray(values, dtype=np.float64)
    if data.ndim != 1 or data.size == 0:
        raise InvalidInputError(f"{name} must be a non-empty list")
    if positive and np.any(data <= 0):
        raise InvalidInputError(f"{name} must be greater than zero")
    return data


def require_period(period: int, name: str = "period") -> None:
    if period < 1:
        raise InvalidInputError(f"{name} must be at least 1")


def require_length(size: int, minimum: int, reason: str) -> None:
    if size < minimum:
        raise InsufficientDataError(
            f"{reason} requires at least {minimum} observations (received {size})"
        )


def same_length(**series: FloatArray) -> int:
    lengths = {name: values.size for name, values in series.items()}
    if len(set(lengths.values())) != 1:
        raise InvalidInputError(f"series must have the same length: {lengths}")
    return next(iter(lengths.values()))


def windows(values: FloatArray, period: int) -> FloatArray:
    """Rolling windows of `period` consecutive values (one row per complete window)."""
    return sliding_window_view(values, period)


# Temporaries created by a per-window reduction (e.g. deviations from the mean) are
# windows × period cells; chunking keeps them near 8 MB instead of up to 100 000 × 1 000 cells.
_WINDOW_CHUNK_CELLS = 1_000_000


def rolling_reduce(
    values: FloatArray, period: int, reducer: Callable[[FloatArray], FloatArray]
) -> FloatArray:
    """Apply `reducer` (rows of windows → one value per row) over rolling windows in chunks."""
    view = windows(values, period)
    step = max(1, _WINDOW_CHUNK_CELLS // period)
    return np.concatenate(
        [reducer(view[start : start + step]) for start in range(0, view.shape[0], step)]
    )


def pad(values: Sequence[float | None] | FloatArray, total: int) -> Series:
    """Left-pad with None so the series aligns with an input of length `total`."""
    items = [None if value is None else float(value) for value in values]
    return [None] * (total - len(items)) + items


def seeded_ema(values: FloatArray, period: int, alpha: float) -> FloatArray:
    """Exponential smoothing seeded with the mean of the first `period` values.

    S_(period−1) = mean(values[0:period]); S_t = α × x_t + (1 − α) × S_(t−1).
    Returns len(values) − period + 1 points.
    """
    smoothed = np.empty(values.size - period + 1)
    smoothed[0] = float(np.mean(values[:period]))
    for index, value in enumerate(values[period:], start=1):
        smoothed[index] = alpha * value + (1 - alpha) * smoothed[index - 1]
    return smoothed


def last(series: Series) -> float | None:
    return series[-1] if series else None


def ratio_index(gains: float, losses: float) -> float:
    """100 − 100 / (1 + gains / losses); 100 when there are no losses, 50 when nothing moved."""
    if losses == 0:
        return 50.0 if gains == 0 else 100.0
    return 100 - 100 / (1 + gains / losses)


def rolling_mean_optional(values: list[float | None], period: int) -> list[float | None]:
    """Rolling mean that is None whenever the window contains an undefined value."""
    result: list[float | None] = []
    for end in range(period, len(values) + 1):
        window = [value for value in values[end - period : end] if value is not None]
        result.append(sum(window) / period if len(window) == period else None)
    return result


@dataclass(frozen=True, slots=True)
class OHLC:
    high: FloatArray
    low: FloatArray
    close: FloatArray

    @property
    def typical_price(self) -> FloatArray:
        return (self.high + self.low + self.close) / 3


def as_ohlc(high: Sequence[float], low: Sequence[float], close: Sequence[float]) -> OHLC:
    bar = OHLC(
        high=as_series(high, "high", positive=True),
        low=as_series(low, "low", positive=True),
        close=as_series(close, "close", positive=True),
    )
    same_length(high=bar.high, low=bar.low, close=bar.close)
    if np.any(bar.high < bar.low):
        raise InvalidInputError("high must be greater than or equal to low in every period")
    if np.any((bar.close > bar.high) | (bar.close < bar.low)):
        raise InvalidInputError("close must lie between low and high in every period")
    return bar


def as_volumes(volumes: Sequence[float], size: int) -> FloatArray:
    data = as_series(volumes, "volumes")
    if np.any(data < 0):
        raise InvalidInputError("volumes must be non-negative")
    if data.size != size:
        raise InvalidInputError("volumes must have the same length as the price series")
    return data
