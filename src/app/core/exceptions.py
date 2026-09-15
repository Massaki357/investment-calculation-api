"""Exceptions reported to API consumers.

Services never import FastAPI. They raise these exceptions, and the error handlers
translate them into the standard error envelope: {"error": {"code", "message", "details"}}.
"""

from typing import Any


class AppError(Exception):
    """Base class for every error intentionally exposed to consumers."""

    code: str = "APP_ERROR"
    status_code: int = 400

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class UnauthorizedError(AppError):
    """Missing or invalid API key (only when authentication is enabled)."""

    code = "UNAUTHORIZED"
    status_code = 401


class CalculationError(AppError):
    """Base class for errors raised by calculation services (HTTP 400)."""

    code = "CALCULATION_ERROR"
    status_code = 400


class InvalidInputError(CalculationError):
    """Input is well-formed but mathematically invalid for the calculation."""

    code = "INVALID_INPUT"


class DivisionByZeroError(CalculationError):
    """A denominator required by the formula is zero."""

    code = "DIVISION_BY_ZERO"


class InsufficientDataError(CalculationError):
    """Not enough observations to compute the result (e.g. series shorter than the period)."""

    code = "INSUFFICIENT_DATA"


class ConvergenceError(CalculationError):
    """A numerical solver (root finding, optimization) did not converge."""

    code = "CONVERGENCE_ERROR"


class NonFiniteResultError(CalculationError):
    """The calculation produced NaN or infinity, which JSON cannot represent."""

    code = "NON_FINITE_RESULT"


class LimitExceededError(CalculationError):
    """The request exceeds a configured safety limit."""

    code = "LIMIT_EXCEEDED"
