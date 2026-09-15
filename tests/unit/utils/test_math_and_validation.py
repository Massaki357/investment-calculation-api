import math

import pytest

from app.core.exceptions import (
    DivisionByZeroError,
    InsufficientDataError,
    InvalidInputError,
    LimitExceededError,
    NonFiniteResultError,
)
from app.utils.math import safe_divide
from app.utils.validation import (
    ensure_finite,
    ensure_max_length,
    ensure_min_length,
    ensure_positive,
)


class TestSafeDivide:
    def test_normal_case_keeps_full_precision(self) -> None:
        assert safe_divide(35.5, 4.2, denominator_name="eps") == 35.5 / 4.2

    def test_negative_denominator_returns_signed_value(self) -> None:
        assert safe_divide(10, -4, denominator_name="eps") == -2.5

    def test_zero_denominator_raises_with_field_name(self) -> None:
        with pytest.raises(DivisionByZeroError, match="eps cannot be zero"):
            safe_divide(10, 0, denominator_name="eps")

    def test_negative_zero_denominator_raises(self) -> None:
        with pytest.raises(DivisionByZeroError):
            safe_divide(10, -0.0, denominator_name="eps")

    def test_overflow_raises_non_finite(self) -> None:
        with pytest.raises(NonFiniteResultError):
            safe_divide(1e308, 1e-10, denominator_name="x")


class TestEnsureFinite:
    def test_finite_value_is_returned(self) -> None:
        assert ensure_finite(1.5, "x") == 1.5

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
    def test_non_finite_values_raise(self, value: float) -> None:
        with pytest.raises(NonFiniteResultError, match="x is not a finite number"):
            ensure_finite(value, "x")


class TestEnsurePositive:
    def test_positive_value_is_returned(self) -> None:
        assert ensure_positive(0.0001, "price") == 0.0001

    @pytest.mark.parametrize("value", [0.0, -1.0])
    def test_zero_and_negative_raise(self, value: float) -> None:
        with pytest.raises(InvalidInputError, match="price must be greater than zero"):
            ensure_positive(value, "price")


class TestLengthGuards:
    def test_min_length_at_boundary_passes(self) -> None:
        ensure_min_length([1, 2], 2, "prices")

    def test_min_length_below_boundary_raises(self) -> None:
        with pytest.raises(InsufficientDataError, match="at least 2 observations"):
            ensure_min_length([1], 2, "prices")

    def test_max_length_at_boundary_passes(self) -> None:
        ensure_max_length([1, 2], 2, "prices")

    def test_max_length_above_boundary_raises(self) -> None:
        with pytest.raises(LimitExceededError, match="at most 2 observations"):
            ensure_max_length([1, 2, 3], 2, "prices")
