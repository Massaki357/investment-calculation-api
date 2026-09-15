from typing import Any

import numpy as np
import pytest
from scipy import stats

from app.core.exceptions import DivisionByZeroError, InsufficientDataError, InvalidInputError
from app.services.statistics import relationships as rel

X = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
Y = [2.3, 3.8, 6.4, 7.7, 10.4, 11.9, 14.2]


class TestCovarianceAndCorrelation:
    def test_covariance_matches_numpy(self) -> None:
        assert rel.covariance(X, Y) == pytest.approx(np.cov(X, Y, ddof=1)[0, 1])
        assert rel.covariance(X, Y, population=True) == pytest.approx(np.cov(X, Y, ddof=0)[0, 1])

    def test_correlation_matches_numpy(self) -> None:
        assert rel.correlation(X, Y) == pytest.approx(np.corrcoef(X, Y)[0, 1])

    def test_perfect_negative_correlation(self) -> None:
        assert rel.correlation(X, [-2 * x for x in X]) == pytest.approx(-1.0)

    def test_r_squared_is_correlation_squared(self) -> None:
        assert rel.r_squared(X, Y) == pytest.approx(np.corrcoef(X, Y)[0, 1] ** 2)

    def test_constant_series(self) -> None:
        with pytest.raises(DivisionByZeroError):
            rel.correlation(X, [1.0] * len(X))

    def test_length_mismatch(self) -> None:
        with pytest.raises(InvalidInputError, match="same length"):
            rel.covariance(X, Y[:-1])


class TestLinearRegression:
    def test_matches_scipy_linregress(self) -> None:
        result = rel.linear_regression(X, Y)
        reference: Any = stats.linregress(X, Y)  # SciPy stubs omit the result attributes

        assert result.slope == pytest.approx(reference.slope)
        assert result.intercept == pytest.approx(reference.intercept)
        assert result.correlation == pytest.approx(reference.rvalue)
        assert result.r_squared == pytest.approx(reference.rvalue**2)
        assert result.slope_standard_error == pytest.approx(reference.stderr)
        assert result.intercept_standard_error == pytest.approx(reference.intercept_stderr)
        assert result.slope_p_value == pytest.approx(reference.pvalue)
        assert result.slope_t_statistic == pytest.approx(reference.slope / reference.stderr)
        assert result.observations == 7

    def test_perfect_fit_edge(self) -> None:
        result = rel.linear_regression([1.0, 2.0, 3.0], [3.0, 5.0, 7.0])

        assert result.slope == pytest.approx(2.0)
        assert result.intercept == pytest.approx(1.0)
        assert result.r_squared == pytest.approx(1.0)
        assert result.slope_t_statistic is None
        assert result.slope_p_value == 0.0

    def test_requires_three_points(self) -> None:
        with pytest.raises(InsufficientDataError):
            rel.linear_regression([1.0, 2.0], [1.0, 2.0])

    def test_constant_x(self) -> None:
        with pytest.raises(DivisionByZeroError, match="x"):
            rel.linear_regression([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])
