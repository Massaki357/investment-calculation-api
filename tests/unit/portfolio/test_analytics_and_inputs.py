import math

import numpy as np
import pytest

from app.core.exceptions import DivisionByZeroError, InsufficientDataError, InvalidInputError
from app.services.portfolio import analytics
from app.services.portfolio.inputs import (
    as_covariance,
    as_weights,
    asset_labels,
    market_from_covariance,
    market_from_returns,
)
from app.services.statistics.relationships import (
    correlation_from_covariance,
    covariance,
    covariance_matrix,
)

COV2 = np.array([[0.04, 0.03], [0.03, 0.09]])  # σ 20% / 30%, ρ = 0.5
W2 = np.array([0.6, 0.4])
RETURNS = [[0.01, 0.02, -0.01], [0.03, -0.01, 0.00], [-0.02, 0.01, 0.02], [0.01, 0.00, 0.01]]


class TestInputs:
    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(InvalidInputError, match="sum to 1"):
            as_weights([0.5, 0.4])

    def test_weights_within_tolerance(self) -> None:
        assert as_weights([0.5, 0.5000001]).sum() == pytest.approx(1.0000001)

    def test_short_weights_are_allowed(self) -> None:
        assert as_weights([1.3, -0.3]).tolist() == [1.3, -0.3]

    @pytest.mark.parametrize(
        ("matrix", "match"),
        [
            ([[0.04, 0.03]], "square"),
            ([[0.04, 0.03], [0.02, 0.09]], "symmetric"),
            ([[0.04, 0.5], [0.5, 0.09]], "positive semi-definite"),
            ([[-0.04, 0.0], [0.0, 0.09]], "non-negative"),
        ],
    )
    def test_invalid_covariance(self, matrix: list[list[float]], match: str) -> None:
        with pytest.raises(InvalidInputError, match=match):
            as_covariance(matrix)

    def test_market_from_returns_annualizes(self) -> None:
        market = market_from_returns(RETURNS, 252)
        data = np.array(RETURNS)
        assert market.expected_returns == pytest.approx(data.mean(axis=0) * 252)
        assert market.covariance == pytest.approx(np.cov(data.T, ddof=1) * 252)

    def test_expected_returns_length_must_match(self) -> None:
        with pytest.raises(InvalidInputError):
            market_from_covariance(COV2.tolist(), [0.1])

    def test_asset_labels(self) -> None:
        assert asset_labels(None, 2) == ["asset_1", "asset_2"]
        with pytest.raises(InvalidInputError, match="unique"):
            asset_labels(["a", "a"], 2)


class TestCovarianceMatrix:
    def test_matches_numpy_and_pairwise_covariance(self) -> None:
        matrix = covariance_matrix(RETURNS)
        columns = np.array(RETURNS).T
        assert matrix == pytest.approx(np.cov(columns, ddof=1))
        assert matrix[0, 1] == pytest.approx(covariance(columns[0].tolist(), columns[1].tolist()))

    def test_constant_column_has_exact_zero_row(self) -> None:
        matrix = covariance_matrix([[0.01, 0.02], [0.01, -0.01], [0.01, 0.03]])
        assert matrix[0].tolist() == [0.0, 0.0]

    def test_requires_two_rows_for_sample(self) -> None:
        with pytest.raises(InsufficientDataError):
            covariance_matrix([[0.01, 0.02]])

    def test_correlation_from_covariance(self) -> None:
        assert correlation_from_covariance(COV2) == pytest.approx(np.array([[1, 0.5], [0.5, 1]]))

    def test_correlation_zero_variance(self) -> None:
        with pytest.raises(DivisionByZeroError):
            correlation_from_covariance(np.array([[0.0, 0.0], [0.0, 0.09]]))


class TestAnalytics:
    def test_expected_return(self) -> None:
        assert analytics.expected_return(W2, np.array([0.10, 0.15])) == pytest.approx(0.12)

    def test_variance_and_volatility(self) -> None:
        # 0.36 × 0.04 + 0.16 × 0.09 + 2 × 0.24 × 0.03 = 0.0432
        assert analytics.variance(W2, COV2) == pytest.approx(0.0432)
        assert analytics.volatility(W2, COV2) == pytest.approx(math.sqrt(0.0432))

    def test_single_asset_edge(self) -> None:
        assert analytics.volatility(np.array([1.0, 0.0]), COV2) == pytest.approx(0.2)

    def test_risk_contributions_sum_to_volatility(self) -> None:
        sigma, items = analytics.risk_contributions(W2, COV2)

        assert sum(item.risk_contribution for item in items) == pytest.approx(sigma)
        assert [item.percent_contribution for item in items] == pytest.approx([0.5, 0.5])
        assert items[0].marginal_contribution == pytest.approx(0.036 / sigma)

    def test_risk_contributions_zero_volatility(self) -> None:
        with pytest.raises(DivisionByZeroError):
            analytics.risk_contributions(W2, np.zeros((2, 2)))

    def test_portfolio_returns(self) -> None:
        weights = np.array([0.5, 0.3, 0.2])
        expected = np.array(RETURNS) @ weights
        assert analytics.portfolio_returns(weights, RETURNS) == pytest.approx(expected)

    def test_concentration(self) -> None:
        result = analytics.concentration([0.5, 0.3, 0.2])

        assert result.hhi == pytest.approx(0.38)
        assert result.effective_number_of_assets == pytest.approx(1 / 0.38)
        assert result.normalized_hhi == pytest.approx((0.38 - 1 / 3) / (2 / 3))
        assert result.max_weight == 0.5

    def test_equal_weights_have_zero_normalized_hhi(self) -> None:
        result = analytics.concentration([0.25] * 4)
        assert result.normalized_hhi == pytest.approx(0)
        assert result.effective_number_of_assets == pytest.approx(4)

    def test_concentration_single_asset_edge(self) -> None:
        result = analytics.concentration([1.0])
        assert result.hhi == 1 and result.normalized_hhi is None

    def test_concentration_rejects_shorts(self) -> None:
        with pytest.raises(InvalidInputError, match="non-negative"):
            analytics.concentration([1.2, -0.2])

    def test_turnover(self) -> None:
        assert analytics.turnover([0.5, 0.3, 0.2], [0.4, 0.4, 0.2]) == pytest.approx(0.1)

    def test_full_rotation_turnover_is_one(self) -> None:
        assert analytics.turnover([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_turnover_length_mismatch(self) -> None:
        with pytest.raises(InvalidInputError):
            analytics.turnover([1.0], [0.5, 0.5])

    def test_weighted_beta(self) -> None:
        assert analytics.weighted_beta(np.array([0.5, 0.3, 0.2]), [1.1, 0.2, 0.8]) == (
            pytest.approx(0.77)
        )

    def test_ex_ante_tracking_error(self) -> None:
        active = W2 - np.array([0.5, 0.5])
        expected = math.sqrt(active @ COV2 @ active)
        assert analytics.ex_ante_tracking_error(W2, np.array([0.5, 0.5]), COV2) == (
            pytest.approx(expected)
        )

    def test_tracking_error_of_benchmark_is_zero(self) -> None:
        assert analytics.ex_ante_tracking_error(W2, W2, COV2) == 0
