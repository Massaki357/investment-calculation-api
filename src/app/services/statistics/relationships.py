"""Relationships between two paired samples."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from app.core.exceptions import DivisionByZeroError, InsufficientDataError, InvalidInputError
from app.services.statistics.descriptive import FloatArray, as_array, ddof_for, is_constant
from app.utils.validation import ensure_finite


def paired_arrays(
    x: Sequence[float],
    y: Sequence[float],
    *,
    x_name: str = "x",
    y_name: str = "y",
    minimum: int = 2,
) -> tuple[FloatArray, FloatArray]:
    if len(x) != len(y):
        raise InvalidInputError(f"{x_name} and {y_name} must have the same length")
    return as_array(x, x_name, minimum), as_array(y, y_name, minimum)


def covariance(
    x: Sequence[float],
    y: Sequence[float],
    *,
    population: bool = False,
    x_name: str = "x",
    y_name: str = "y",
) -> float:
    """Covariance = Σ (x − x̄)(y − ȳ) / (n − ddof); ddof = 1 (sample) unless population."""
    ddof = ddof_for(population)
    xs, ys = paired_arrays(x, y, x_name=x_name, y_name=y_name, minimum=ddof + 1)
    if is_constant(xs) or is_constant(ys):
        return 0.0
    products = (xs - xs.mean()) * (ys - ys.mean())
    return ensure_finite(math.fsum(products.tolist()) / (len(xs) - ddof), "covariance")


def correlation(
    x: Sequence[float], y: Sequence[float], *, x_name: str = "x", y_name: str = "y"
) -> float:
    """Pearson correlation = Σ (x − x̄)(y − ȳ) / √(Σ (x − x̄)² × Σ (y − ȳ)²)."""
    xs, ys = paired_arrays(x, y, x_name=x_name, y_name=y_name)
    if is_constant(xs) or is_constant(ys):
        raise DivisionByZeroError("correlation is undefined when a series has zero variance")
    x_dev, y_dev = xs - xs.mean(), ys - ys.mean()
    denominator = math.sqrt(float(np.dot(x_dev, x_dev)) * float(np.dot(y_dev, y_dev)))
    if denominator == 0:
        raise DivisionByZeroError("correlation is undefined when a series has zero variance")
    return max(-1.0, min(1.0, float(np.dot(x_dev, y_dev)) / denominator))


def covariance_matrix(
    observations: Sequence[Sequence[float]], *, population: bool = False
) -> FloatArray:
    """Covariance matrix of columns (rows = observations, columns = variables).

    Σ_ij = Σ_t (x_ti − x̄_i)(x_tj − x̄_j) / (T − ddof); constant columns get exactly zero rows.
    """
    ddof = ddof_for(population)
    data = np.asarray(observations, dtype=np.float64)
    if data.ndim != 2 or data.shape[1] == 0:
        raise InvalidInputError("observations must be a non-empty rectangular matrix")
    if data.shape[0] < ddof + 1:
        raise InsufficientDataError(f"at least {ddof + 1} observations are required")
    deviations = data - data.mean(axis=0)
    constant = np.ptp(data, axis=0) == 0
    deviations[:, constant] = 0.0
    matrix = deviations.T @ deviations / (data.shape[0] - ddof)
    if not np.all(np.isfinite(matrix)):
        raise InvalidInputError("covariance matrix is not finite")
    return matrix


def correlation_from_covariance(matrix: FloatArray) -> FloatArray:
    """ρ_ij = Σ_ij / (σ_i σ_j); undefined when a variable has zero variance."""
    variances = np.diag(matrix)
    if np.any(variances <= 0):
        raise DivisionByZeroError("correlation is undefined when a variable has zero variance")
    scale = np.sqrt(variances)
    correlation_matrix = np.clip(matrix / np.outer(scale, scale), -1.0, 1.0)
    np.fill_diagonal(correlation_matrix, 1.0)
    return correlation_matrix


def r_squared(
    x: Sequence[float], y: Sequence[float], *, x_name: str = "x", y_name: str = "y"
) -> float:
    """R² of the simple linear regression of y on x = correlation²."""
    return correlation(x, y, x_name=x_name, y_name=y_name) ** 2


@dataclass(frozen=True, slots=True)
class LinearRegression:
    slope: float
    intercept: float
    correlation: float
    r_squared: float
    residual_standard_error: float
    slope_standard_error: float
    intercept_standard_error: float
    slope_t_statistic: float | None
    slope_p_value: float
    observations: int


def linear_regression(
    x: Sequence[float], y: Sequence[float], *, x_name: str = "x", y_name: str = "y"
) -> LinearRegression:
    """Ordinary least squares y = intercept + slope × x.

    slope = Sxy / Sxx, intercept = ȳ − slope × x̄
    s² = Σ residual² / (n − 2)
    SE(slope) = √(s² / Sxx), SE(intercept) = √(s² × (1/n + x̄² / Sxx))
    t = slope / SE(slope), two-sided p-value from Student's t with n − 2 degrees of freedom
    """
    xs, ys = paired_arrays(x, y, x_name=x_name, y_name=y_name)
    n = len(xs)
    if n < 3:
        raise InsufficientDataError("linear regression requires at least 3 observations")

    x_mean, y_mean = float(xs.mean()), float(ys.mean())
    x_dev, y_dev = xs - x_mean, ys - y_mean
    sxx = float(np.dot(x_dev, x_dev))
    syy = float(np.dot(y_dev, y_dev))
    if is_constant(xs):
        raise DivisionByZeroError(f"regression is undefined when {x_name} has zero variance")
    if is_constant(ys):
        raise DivisionByZeroError(f"R² is undefined when {y_name} has zero variance")

    slope = float(np.dot(x_dev, y_dev)) / sxx
    intercept = y_mean - slope * x_mean
    residuals = ys - (intercept + slope * xs)
    residual_variance = float(np.dot(residuals, residuals)) / (n - 2)
    slope_se = math.sqrt(residual_variance / sxx)
    intercept_se = math.sqrt(residual_variance * (1 / n + x_mean**2 / sxx))

    if slope_se == 0:
        t_statistic, p_value = None, 0.0
    else:
        t_statistic = slope / slope_se
        p_value = float(2 * stats.t.sf(abs(t_statistic), n - 2))

    correlation_value = max(-1.0, min(1.0, float(np.dot(x_dev, y_dev)) / math.sqrt(sxx * syy)))
    return LinearRegression(
        slope=ensure_finite(slope, "slope"),
        intercept=ensure_finite(intercept, "intercept"),
        correlation=correlation_value,
        r_squared=correlation_value**2,
        residual_standard_error=math.sqrt(residual_variance),
        slope_standard_error=slope_se,
        intercept_standard_error=intercept_se,
        slope_t_statistic=t_statistic,
        slope_p_value=p_value,
        observations=n,
    )
