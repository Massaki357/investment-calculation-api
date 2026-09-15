"""Return series transformations, compounding and annualization."""

import math
from collections.abc import Sequence
from enum import StrEnum

import numpy as np

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.services.statistics.descriptive import FloatArray, as_array
from app.utils.validation import ensure_finite


class ReturnType(StrEnum):
    SIMPLE = "simple"
    LOG = "log"


def returns_from_prices(prices: Sequence[float], return_type: ReturnType) -> list[float]:
    """simple: P_t / P_{t−1} − 1 · log: ln(P_t / P_{t−1})."""
    data = as_array(prices, "prices", minimum=2)
    if np.any(data <= 0):
        raise InvalidInputError("prices must be greater than zero")
    ratios = data[1:] / data[:-1]
    result = np.log(ratios) if return_type is ReturnType.LOG else ratios - 1
    return [float(item) for item in result]


def validate_returns(returns: Sequence[float], return_type: ReturnType, name: str) -> FloatArray:
    data = as_array(returns, name)
    if return_type is ReturnType.SIMPLE and np.any(data <= -1):
        raise InvalidInputError(f"simple {name} must be greater than -1 (a loss above 100%)")
    return data


def wealth_index(returns: Sequence[float], return_type: ReturnType) -> list[float]:
    """Growth of 1 unit: W_0 = 1, W_t = W_{t−1} × (1 + r_t) (simple) or × e^{r_t} (log)."""
    data = validate_returns(returns, return_type, "returns")
    with np.errstate(over="ignore"):
        growth = np.exp(np.cumsum(data)) if return_type is ReturnType.LOG else np.cumprod(1 + data)
    if not np.all(np.isfinite(growth)):
        raise NonFiniteResultError("cumulative growth is too large to be represented")
    return [1.0, *(float(item) for item in growth)]


def cumulative_return(returns: Sequence[float], return_type: ReturnType) -> float:
    """Cumulative return = Π(1 + r_t) − 1 (simple) or e^{Σ r_t} − 1 (log)."""
    return wealth_index(returns, return_type)[-1] - 1


def annualized_return(
    returns: Sequence[float], return_type: ReturnType, periods_per_year: float
) -> float:
    """Geometric annualized return = (1 + cumulative)^(periods_per_year / n) − 1."""
    growth = wealth_index(returns, return_type)[-1]
    try:
        result = growth ** (periods_per_year / len(returns)) - 1
    except OverflowError as exc:
        raise NonFiniteResultError("annualized return is too large to be represented") from exc
    return ensure_finite(result, "annualized return")


def periodic_rate(annual_rate: float, periods_per_year: float, return_type: ReturnType) -> float:
    """Annual rate expressed per return period: (1 + r)^(1/ppy) − 1 or ln(1 + r) / ppy."""
    if annual_rate <= -1:
        raise InvalidInputError("annual rates must be greater than -1")
    if return_type is ReturnType.LOG:
        return math.log1p(annual_rate) / periods_per_year
    return (1 + annual_rate) ** (1 / periods_per_year) - 1


def annualize_dispersion(periodic_value: float, periods_per_year: float) -> float:
    """Annualized standard deviation = periodic × √periods_per_year."""
    return periodic_value * math.sqrt(periods_per_year)
