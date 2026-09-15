"""Numeric helpers shared by calculation services. No rounding is ever applied."""

from app.core.exceptions import DivisionByZeroError
from app.utils.validation import ensure_finite


def safe_divide(numerator: float, denominator: float, *, denominator_name: str) -> float:
    """Divide, raising DivisionByZeroError when the denominator is exactly zero.

    Negative denominators are allowed: the signed result is returned without interpretation.
    """
    if denominator == 0:
        raise DivisionByZeroError(f"{denominator_name} cannot be zero")
    return ensure_finite(numerator / denominator, "result")
