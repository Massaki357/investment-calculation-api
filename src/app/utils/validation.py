"""Reusable guards for calculation services. Each raises a domain exception on failure."""

import math
from collections.abc import Sized

from app.core.exceptions import (
    InsufficientDataError,
    InvalidInputError,
    LimitExceededError,
    NonFiniteResultError,
)


def ensure_finite(value: float, name: str) -> float:
    """Return `value` unchanged, or raise if it is NaN or +/-infinity."""
    if not math.isfinite(value):
        raise NonFiniteResultError(f"{name} is not a finite number")
    return value


def ensure_positive(value: float, name: str) -> float:
    """Return `value` unchanged, or raise if it is not strictly greater than zero."""
    if value <= 0:
        raise InvalidInputError(f"{name} must be greater than zero")
    return value


def ensure_min_length(values: Sized, minimum: int, name: str) -> None:
    if len(values) < minimum:
        raise InsufficientDataError(
            f"{name} must contain at least {minimum} observations (received {len(values)})"
        )


def ensure_max_length(values: Sized, maximum: int, name: str) -> None:
    if len(values) > maximum:
        raise LimitExceededError(
            f"{name} must contain at most {maximum} observations (received {len(values)})"
        )
