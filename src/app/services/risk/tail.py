"""Value at Risk and expected shortfall (conditional VaR), reported as positive losses."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from app.core.exceptions import InvalidInputError
from app.services.statistics.descriptive import as_array, mean, standard_deviation


@dataclass(frozen=True, slots=True)
class TailRisk:
    value_at_risk: float
    expected_shortfall: float
    confidence: float
    horizon_periods: int


def _validate(confidence: float, horizon_periods: int) -> None:
    if not 0 < confidence < 1:
        raise InvalidInputError("confidence must be between 0 and 1")
    if horizon_periods < 1:
        raise InvalidInputError("horizon_periods must be at least 1")


def historical_tail_risk(
    returns: Sequence[float], confidence: float = 0.95, horizon_periods: int = 1
) -> TailRisk:
    """Historical simulation.

    q = empirical quantile of returns at (1 − confidence), linear interpolation
    VaR_1 = −q · ES_1 = −mean(returns ≤ q)
    Horizon scaling (square-root-of-time approximation): VaR_h = VaR_1 × √h, ES_h = ES_1 × √h
    """
    _validate(confidence, horizon_periods)
    data = as_array(returns, "returns", minimum=2)
    quantile = float(np.quantile(data, 1 - confidence, method="linear"))
    tail = data[data <= quantile]
    scale = math.sqrt(horizon_periods)
    return TailRisk(
        value_at_risk=-quantile * scale,
        expected_shortfall=-float(tail.mean()) * scale,
        confidence=confidence,
        horizon_periods=horizon_periods,
    )


def parametric_tail_risk(
    returns: Sequence[float],
    confidence: float = 0.95,
    horizon_periods: int = 1,
    *,
    include_mean: bool = True,
) -> TailRisk:
    """Normal (variance-covariance) method.

    μ_h = μ × h (0 when include_mean is false), σ_h = σ × √h, z = Φ⁻¹(confidence)
    VaR = −(μ_h − z σ_h) · ES = −(μ_h − σ_h φ(z) / (1 − confidence))
    """
    _validate(confidence, horizon_periods)
    mu = mean(returns) * horizon_periods if include_mean else 0.0
    sigma = standard_deviation(returns) * math.sqrt(horizon_periods)
    z = float(stats.norm.ppf(confidence))
    return TailRisk(
        value_at_risk=-(mu - z * sigma),
        expected_shortfall=-(mu - sigma * float(stats.norm.pdf(z)) / (1 - confidence)),
        confidence=confidence,
        horizon_periods=horizon_periods,
    )
