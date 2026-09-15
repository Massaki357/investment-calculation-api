"""Portfolio return, risk, attribution and composition metrics."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.portfolio.inputs import as_long_only, as_returns_matrix, as_weights
from app.services.statistics.descriptive import FloatArray
from app.utils.validation import ensure_finite


def expected_return(weights: FloatArray, expected_returns: FloatArray) -> float:
    """E(R_p) = Σ w_i × E(R_i)."""
    if weights.shape != expected_returns.shape:
        raise InvalidInputError("weights and expected_returns must have the same length")
    return ensure_finite(float(weights @ expected_returns), "expected return")


def variance(weights: FloatArray, covariance: FloatArray) -> float:
    """σ²_p = wᵀ Σ w."""
    if weights.shape[0] != covariance.shape[0]:
        raise InvalidInputError("weights must have one entry per asset in the covariance matrix")
    return max(0.0, ensure_finite(float(weights @ covariance @ weights), "variance"))


def volatility(weights: FloatArray, covariance: FloatArray) -> float:
    """σ_p = √(wᵀ Σ w)."""
    return math.sqrt(variance(weights, covariance))


def portfolio_returns(weights: FloatArray, returns: Sequence[Sequence[float]]) -> list[float]:
    """r_p,t = Σ_i w_i r_i,t (constant weights, rebalanced every period)."""
    data = as_returns_matrix(returns)
    if data.shape[1] != weights.shape[0]:
        raise InvalidInputError("weights must have one entry per returns column")
    return [float(value) for value in data @ weights]


@dataclass(frozen=True, slots=True)
class RiskContribution:
    weight: float
    marginal_contribution: float
    risk_contribution: float
    percent_contribution: float


def risk_contributions(
    weights: FloatArray, covariance: FloatArray
) -> tuple[float, list[RiskContribution]]:
    """Euler decomposition of volatility.

    MRC_i = (Σ w)_i / σ_p, RC_i = w_i × MRC_i (Σ RC_i = σ_p), %RC_i = RC_i / σ_p
    """
    sigma = volatility(weights, covariance)
    if sigma == 0:
        raise DivisionByZeroError(
            "risk contributions are undefined for a zero-volatility portfolio"
        )
    marginal = covariance @ weights / sigma
    contributions = weights * marginal
    return sigma, [
        RiskContribution(
            weight=float(w),
            marginal_contribution=float(m),
            risk_contribution=float(c),
            percent_contribution=float(c / sigma),
        )
        for w, m, c in zip(weights, marginal, contributions, strict=True)
    ]


@dataclass(frozen=True, slots=True)
class Concentration:
    hhi: float
    normalized_hhi: float | None
    effective_number_of_assets: float
    max_weight: float
    number_of_assets: int


def concentration(weights: Sequence[float]) -> Concentration:
    """HHI = Σ w_i²; effective N = 1 / HHI; normalized HHI = (HHI − 1/N) / (1 − 1/N)."""
    data = as_long_only(as_weights(weights))
    n = int(data.size)
    hhi = float(np.sum(data**2))
    return Concentration(
        hhi=hhi,
        normalized_hhi=None if n == 1 else (hhi - 1 / n) / (1 - 1 / n),
        effective_number_of_assets=1 / hhi,
        max_weight=float(data.max()),
        number_of_assets=n,
    )


def turnover(current_weights: Sequence[float], target_weights: Sequence[float]) -> float:
    """One-way turnover = Σ |w_target − w_current| / 2."""
    current = np.asarray(current_weights, dtype=np.float64)
    target = np.asarray(target_weights, dtype=np.float64)
    if current.shape != target.shape or current.size == 0:
        raise InvalidInputError("current_weights and target_weights must have the same length")
    return float(np.sum(np.abs(target - current))) / 2


def weighted_beta(weights: FloatArray, asset_betas: Sequence[float]) -> float:
    """β_p = Σ w_i β_i."""
    betas = np.asarray(asset_betas, dtype=np.float64)
    if betas.shape != weights.shape:
        raise InvalidInputError("asset_betas must have one entry per weight")
    return float(weights @ betas)


def ex_ante_tracking_error(
    weights: FloatArray, benchmark_weights: FloatArray, covariance: FloatArray
) -> float:
    """TE = √((w − w_b)ᵀ Σ (w − w_b))."""
    active = weights - benchmark_weights
    if active.shape[0] != covariance.shape[0]:
        raise InvalidInputError("weights must have one entry per asset in the covariance matrix")
    return math.sqrt(max(0.0, float(active @ covariance @ active)))
