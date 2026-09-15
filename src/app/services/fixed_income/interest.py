"""Simple, periodic and continuous compounding."""

import math

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.utils.validation import ensure_finite


def _power(base: float, exponent: float) -> float:
    try:
        return ensure_finite(base**exponent, "growth factor")
    except OverflowError as exc:
        raise NonFiniteResultError("growth factor is too large to be represented") from exc


def _exp(exponent: float) -> float:
    try:
        return math.exp(exponent)
    except OverflowError as exc:
        raise NonFiniteResultError("growth factor is too large to be represented") from exc


def simple_growth_factor(rate: float, years: float) -> float:
    """Simple interest factor = 1 + rate × years."""
    return ensure_finite(1 + rate * years, "growth factor")


def periodic_growth_factor(rate: float, years: float, frequency: int) -> float:
    """Periodic compounding factor = (1 + rate / frequency) ^ (frequency × years)."""
    if frequency < 1:
        raise InvalidInputError("compounding_frequency must be at least 1")
    if rate / frequency <= -1:
        raise InvalidInputError("rate / compounding_frequency must be greater than -1")
    return _power(1 + rate / frequency, frequency * years)


def continuous_growth_factor(rate: float, years: float) -> float:
    """Continuous compounding factor = e ^ (rate × years)."""
    return _exp(rate * years)


def interest_amount(principal: float, growth_factor: float) -> tuple[float, float]:
    """Return (interest, future_value) with future_value = principal × growth_factor."""
    future_value = ensure_finite(principal * growth_factor, "future value")
    return ensure_finite(future_value - principal, "interest"), future_value


def discount(amount: float, growth_factor: float) -> float:
    """Present value = amount / growth_factor."""
    if growth_factor <= 0:
        raise InvalidInputError("the growth factor must be positive to discount a value")
    return ensure_finite(amount / growth_factor, "present value")
