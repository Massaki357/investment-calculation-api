"""Descriptive statistics of a single sample."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from scipy import stats

from app.core.exceptions import DivisionByZeroError, InsufficientDataError, InvalidInputError
from app.utils.validation import ensure_finite, ensure_min_length

FloatArray = NDArray[np.float64]


def as_array(values: Sequence[float], name: str, minimum: int = 1) -> FloatArray:
    ensure_min_length(values, minimum, name)
    return np.asarray(values, dtype=np.float64)


def ddof_for(population: bool) -> int:
    return 0 if population else 1


def is_constant(data: FloatArray) -> bool:
    """Exact zero-variance check (floating-point means of equal values are not always exact)."""
    return float(np.ptp(data)) == 0.0


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean = Σ x / n."""
    return ensure_finite(math.fsum(values) / len(as_array(values, "values")), "mean")


def median(values: Sequence[float]) -> float:
    """Median: middle value (average of the two middle values when n is even)."""
    return float(np.median(as_array(values, "values")))


def variance(values: Sequence[float], *, population: bool = False) -> float:
    """Variance = Σ (x − mean)² / (n − ddof); ddof = 1 (sample) unless population."""
    ddof = ddof_for(population)
    data = as_array(values, "values", minimum=ddof + 1)
    if is_constant(data):
        return 0.0
    return ensure_finite(float(np.var(data, ddof=ddof)), "variance")


def standard_deviation(values: Sequence[float], *, population: bool = False) -> float:
    """Standard deviation = √variance."""
    return math.sqrt(variance(values, population=population))


class PercentileMethod(StrEnum):
    LINEAR = "linear"
    LOWER = "lower"
    HIGHER = "higher"
    MIDPOINT = "midpoint"
    NEAREST = "nearest"


def percentiles(
    values: Sequence[float],
    percentile_ranks: Sequence[float],
    method: PercentileMethod = PercentileMethod.LINEAR,
) -> list[float]:
    """Percentiles at the requested ranks (0-100), interpolated with `method`."""
    data = as_array(values, "values")
    if any(rank < 0 or rank > 100 for rank in percentile_ranks):
        raise InvalidInputError("percentiles must be between 0 and 100")
    result = np.percentile(
        data, np.asarray(percentile_ranks, dtype=np.float64), method=method.value
    )
    return [float(item) for item in np.atleast_1d(result)]


@dataclass(frozen=True, slots=True)
class Quartiles:
    q1: float
    q2: float
    q3: float

    @property
    def interquartile_range(self) -> float:
        return self.q3 - self.q1


def quartiles(
    values: Sequence[float], method: PercentileMethod = PercentileMethod.LINEAR
) -> Quartiles:
    """Q1, Q2 (median) and Q3 as the 25th, 50th and 75th percentiles."""
    q1, q2, q3 = percentiles(values, [25, 50, 75], method)
    return Quartiles(q1=q1, q2=q2, q3=q3)


@dataclass(frozen=True, slots=True)
class ZScores:
    mean: float
    standard_deviation: float
    z_scores: list[float]
    observation_z_score: float | None


def z_scores(
    values: Sequence[float], observation: float | None = None, *, population: bool = False
) -> ZScores:
    """z = (x − mean) / standard deviation, for every value and an optional observation."""
    average = mean(values)
    deviation = standard_deviation(values, population=population)
    if deviation == 0:
        raise DivisionByZeroError("values have zero standard deviation")
    return ZScores(
        mean=average,
        standard_deviation=deviation,
        z_scores=[(value - average) / deviation for value in values],
        observation_z_score=None if observation is None else (observation - average) / deviation,
    )


def _central_moments(values: Sequence[float]) -> tuple[int, float, float, float]:
    data = as_array(values, "values")
    if is_constant(data):
        raise DivisionByZeroError("values have zero variance")
    deviations = data - data.mean()
    m2 = float(np.mean(deviations**2))
    return len(data), m2, float(np.mean(deviations**3)), float(np.mean(deviations**4))


def skewness(values: Sequence[float], *, bias_corrected: bool = True) -> float:
    """Skewness.

    g1 = m3 / m2^(3/2) (population moments)
    G1 = g1 × √(n (n − 1)) / (n − 2)   (adjusted Fisher-Pearson, default, n ≥ 3)
    """
    n, m2, m3, _ = _central_moments(values)
    g1 = m3 / m2**1.5
    if not bias_corrected:
        return ensure_finite(g1, "skewness")
    if n < 3:
        raise InsufficientDataError("bias-corrected skewness requires at least 3 observations")
    return ensure_finite(g1 * math.sqrt(n * (n - 1)) / (n - 2), "skewness")


def kurtosis(values: Sequence[float], *, excess: bool = True, bias_corrected: bool = True) -> float:
    """Kurtosis.

    g2 = m4 / m2² − 3 (population excess kurtosis)
    G2 = [(n + 1) g2 + 6] × (n − 1) / ((n − 2)(n − 3))   (bias-corrected, default, n ≥ 4)
    Non-excess (Pearson) kurtosis adds 3.
    """
    n, m2, _, m4 = _central_moments(values)
    g2 = m4 / m2**2 - 3
    if bias_corrected:
        if n < 4:
            raise InsufficientDataError("bias-corrected kurtosis requires at least 4 observations")
        g2 = ((n + 1) * g2 + 6) * (n - 1) / ((n - 2) * (n - 3))
    return ensure_finite(g2 if excess else g2 + 3, "kurtosis")


@dataclass(frozen=True, slots=True)
class MeanConfidenceInterval:
    mean: float
    lower: float
    upper: float
    margin_of_error: float
    standard_error: float
    critical_value: float
    degrees_of_freedom: int


def confidence_interval_mean(
    values: Sequence[float], confidence: float = 0.95
) -> MeanConfidenceInterval:
    """Mean ± t_(1+c)/2, n−1 × s / √n (Student's t, sample standard deviation)."""
    if not 0 < confidence < 1:
        raise InvalidInputError("confidence must be between 0 and 1")
    data = as_array(values, "values", minimum=2)
    average = mean(values)
    standard_error = standard_deviation(values) / math.sqrt(len(data))
    degrees = len(data) - 1
    critical = float(stats.t.ppf((1 + confidence) / 2, degrees))
    margin = critical * standard_error
    return MeanConfidenceInterval(
        mean=average,
        lower=average - margin,
        upper=average + margin,
        margin_of_error=margin,
        standard_error=standard_error,
        critical_value=critical,
        degrees_of_freedom=degrees,
    )
