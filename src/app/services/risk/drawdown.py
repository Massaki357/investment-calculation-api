"""Maximum drawdown of a wealth (or price) path."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError


@dataclass(frozen=True, slots=True)
class Drawdown:
    max_drawdown: float
    peak_index: int | None
    trough_index: int | None
    recovery_index: int | None

    @property
    def duration_periods(self) -> int | None:
        """Periods from peak to trough."""
        if self.peak_index is None or self.trough_index is None:
            return None
        return self.trough_index - self.peak_index


def maximum_drawdown(path: Sequence[float]) -> Drawdown:
    """MDD = min_t (W_t / max_{s≤t} W_s − 1), reported as a negative decimal (0 if none).

    Indices refer to positions in `path`. The recovery index is the first later position at or
    above the peak (null if the path never recovers).
    """
    if len(path) < 2:
        raise InvalidInputError("maximum drawdown requires at least 2 points")
    if any(value <= 0 for value in path):
        raise InvalidInputError("prices / wealth values must be greater than zero")

    running_peak_value = path[0]
    running_peak_index = 0
    worst = 0.0
    peak_index: int | None = None
    trough_index: int | None = None
    for index, value in enumerate(path):
        if value > running_peak_value:
            running_peak_value, running_peak_index = value, index
        drawdown = value / running_peak_value - 1
        if drawdown < worst:
            worst, peak_index, trough_index = drawdown, running_peak_index, index

    recovery_index = None
    if peak_index is not None and trough_index is not None:
        peak_value = path[peak_index]
        recovery_index = next(
            (i for i in range(trough_index + 1, len(path)) if path[i] >= peak_value), None
        )
    return Drawdown(
        max_drawdown=worst,
        peak_index=peak_index,
        trough_index=trough_index,
        recovery_index=recovery_index,
    )
