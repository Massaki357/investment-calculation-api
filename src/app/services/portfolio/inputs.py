"""Validation and estimation of portfolio inputs."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.exceptions import InvalidInputError
from app.services.statistics.descriptive import FloatArray
from app.services.statistics.relationships import covariance_matrix

WEIGHT_SUM_TOLERANCE = 1e-6
_SYMMETRY_TOLERANCE = 1e-10
_PSD_TOLERANCE = 1e-10


def as_weights(
    weights: Sequence[float], *, name: str = "weights", n_assets: int | None = None
) -> FloatArray:
    data = np.asarray(weights, dtype=np.float64)
    if data.ndim != 1 or data.size == 0:
        raise InvalidInputError(f"{name} must be a non-empty list")
    if n_assets is not None and data.size != n_assets:
        raise InvalidInputError(f"{name} must have one entry per asset ({n_assets})")
    total = float(data.sum())
    if abs(total - 1) > WEIGHT_SUM_TOLERANCE:
        raise InvalidInputError(f"{name} must sum to 1 (received {total})")
    return data


def as_long_only(weights: FloatArray, name: str = "weights") -> FloatArray:
    if np.any(weights < 0):
        raise InvalidInputError(f"{name} must be non-negative for this calculation")
    return weights


def as_covariance(matrix: Sequence[Sequence[float]]) -> FloatArray:
    """Validate a covariance matrix: square, symmetric and positive semi-definite."""
    if not matrix or any(len(row) != len(matrix) for row in matrix):
        raise InvalidInputError("covariance_matrix must be a non-empty square matrix")
    data = np.asarray(matrix, dtype=np.float64)
    scale = max(float(np.max(np.abs(data))), 1e-300)
    if not np.allclose(data, data.T, rtol=0, atol=_SYMMETRY_TOLERANCE * scale):
        raise InvalidInputError("covariance_matrix must be symmetric")
    if np.any(np.diag(data) < 0):
        raise InvalidInputError("covariance_matrix diagonal (variances) must be non-negative")
    eigenvalues = np.linalg.eigvalsh((data + data.T) / 2)
    if float(eigenvalues.min()) < -_PSD_TOLERANCE * max(float(np.abs(eigenvalues).max()), 1.0):
        raise InvalidInputError("covariance_matrix must be positive semi-definite")
    return (data + data.T) / 2


def as_returns_matrix(returns: Sequence[Sequence[float]], *, minimum_rows: int = 1) -> FloatArray:
    rows = [len(row) for row in returns]
    if not rows or len(set(rows)) != 1 or rows[0] == 0:
        raise InvalidInputError("returns must be a rectangular matrix (periods × assets)")
    data = np.asarray(returns, dtype=np.float64)
    if data.shape[0] < minimum_rows:
        raise InvalidInputError(f"returns must contain at least {minimum_rows} periods")
    if np.any(data <= -1):
        raise InvalidInputError("simple returns must be greater than -1")
    return data


@dataclass(frozen=True, slots=True)
class MarketInputs:
    covariance: FloatArray
    expected_returns: FloatArray | None

    @property
    def n_assets(self) -> int:
        return int(self.covariance.shape[0])


def market_from_returns(
    returns: Sequence[Sequence[float]], periods_per_year: float
) -> MarketInputs:
    """Annualized estimates: μ = mean × ppy, Σ = sample covariance × ppy."""
    data = as_returns_matrix(returns, minimum_rows=2)
    return MarketInputs(
        covariance=covariance_matrix(data.tolist()) * periods_per_year,
        expected_returns=data.mean(axis=0) * periods_per_year,
    )


def market_from_covariance(
    matrix: Sequence[Sequence[float]], expected_returns: Sequence[float] | None
) -> MarketInputs:
    covariance = as_covariance(matrix)
    mu = None
    if expected_returns is not None:
        mu = np.asarray(expected_returns, dtype=np.float64)
        if mu.shape != (covariance.shape[0],):
            raise InvalidInputError("expected_returns must have one entry per asset")
    return MarketInputs(covariance=covariance, expected_returns=mu)


def require_expected_returns(market: MarketInputs) -> FloatArray:
    if market.expected_returns is None:
        raise InvalidInputError("expected_returns are required for this calculation")
    return market.expected_returns


def asset_labels(names: Sequence[str] | None, n_assets: int) -> list[str]:
    if names is None:
        return [f"asset_{index}" for index in range(1, n_assets + 1)]
    if len(names) != n_assets:
        raise InvalidInputError(f"asset_names must have one entry per asset ({n_assets})")
    if len(set(names)) != len(names):
        raise InvalidInputError("asset_names must be unique")
    return list(names)
