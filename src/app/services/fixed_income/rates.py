"""Interest rate conversions."""

import math

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.utils.validation import ensure_finite


def effective_from_nominal(nominal_rate: float, compounding_frequency: int) -> float:
    """Effective annual rate = (1 + nominal / m) ^ m − 1."""
    if compounding_frequency < 1:
        raise InvalidInputError("compounding_frequency must be at least 1")
    if nominal_rate / compounding_frequency <= -1:
        raise InvalidInputError("nominal_rate / compounding_frequency must be greater than -1")
    try:
        result = (1 + nominal_rate / compounding_frequency) ** compounding_frequency - 1
    except OverflowError as exc:
        raise NonFiniteResultError("effective rate is too large to be represented") from exc
    return ensure_finite(result, "effective rate")


def effective_from_continuous(nominal_rate: float) -> float:
    """Effective annual rate under continuous compounding = e ^ nominal − 1."""
    try:
        return math.expm1(nominal_rate)
    except OverflowError as exc:
        raise NonFiniteResultError("effective rate is too large to be represented") from exc


def nominal_from_effective(effective_rate: float, compounding_frequency: int) -> float:
    """Nominal annual rate = m × [(1 + effective) ^ (1 / m) − 1]."""
    if compounding_frequency < 1:
        raise InvalidInputError("compounding_frequency must be at least 1")
    if effective_rate <= -1:
        raise InvalidInputError("effective_rate must be greater than -1")
    return compounding_frequency * ((1 + effective_rate) ** (1 / compounding_frequency) - 1)


def real_rate_exact(nominal_rate: float, inflation_rate: float) -> float:
    """Fisher (exact): real = (1 + nominal) / (1 + inflation) − 1."""
    if inflation_rate <= -1:
        raise InvalidInputError("inflation_rate must be greater than -1")
    return (1 + nominal_rate) / (1 + inflation_rate) - 1


def real_rate_approximate(nominal_rate: float, inflation_rate: float) -> float:
    """Fisher (approximation): real ≈ nominal − inflation."""
    return nominal_rate - inflation_rate


def convert_effective_rate(rate: float, from_years: float, to_years: float) -> float:
    """Equivalent compound rate: r_to = (1 + r_from) ^ (to_years / from_years) − 1."""
    if rate <= -1:
        raise InvalidInputError("rate must be greater than -1")
    if from_years <= 0 or to_years <= 0:
        raise InvalidInputError("period lengths must be greater than zero")
    try:
        result = (1 + rate) ** (to_years / from_years) - 1
    except OverflowError as exc:
        raise NonFiniteResultError("converted rate is too large to be represented") from exc
    return ensure_finite(result, "converted rate")
