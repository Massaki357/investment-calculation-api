import numpy as np
import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.portfolio import analytics, optimization
from app.services.portfolio.inputs import MarketInputs, market_from_covariance, market_from_returns

COV2 = [[0.04, 0.03], [0.03, 0.09]]
MU2 = [0.10, 0.15]
COV3 = [[0.04, 0.006, 0.002], [0.006, 0.09, 0.018], [0.002, 0.018, 0.0225]]
MU3 = [0.08, 0.14, 0.06]


def market2() -> MarketInputs:
    return market_from_covariance(COV2, MU2)


def market3() -> MarketInputs:
    return market_from_covariance(COV3, MU3)


class TestMinimumVariance:
    def test_two_asset_closed_form(self) -> None:
        # w1 = (σ2² − σ12) / (σ1² + σ2² − 2σ12) = 0.06 / 0.07
        weights = optimization.minimum_variance(market2())
        assert weights == pytest.approx([6 / 7, 1 / 7], abs=1e-7)

    def test_no_feasible_portfolio_has_lower_variance(self) -> None:
        market = market3()
        best = analytics.variance(optimization.minimum_variance(market), market.covariance)
        rng = np.random.default_rng(7)
        for candidate in rng.dirichlet(np.ones(3), size=500):
            assert analytics.variance(candidate, market.covariance) >= best - 1e-12

    def test_upper_bound_is_respected(self) -> None:
        weights = optimization.minimum_variance(market2(), 0.0, 0.7)
        assert weights == pytest.approx([0.7, 0.3], abs=1e-7)

    def test_infeasible_bounds(self) -> None:
        with pytest.raises(InvalidInputError, match="cannot sum to 1"):
            optimization.minimum_variance(market3(), 0.0, 0.3)

    def test_from_returns_matrix(self) -> None:
        rng = np.random.default_rng(3)
        market = market_from_returns(rng.normal(0.0005, 0.01, size=(120, 4)).tolist(), 252)
        weights = optimization.minimum_variance(market)
        assert weights.sum() == pytest.approx(1)
        assert np.all(weights >= -1e-9)


class TestMaximumSharpe:
    def test_two_asset_tangency_closed_form(self) -> None:
        # w ∝ Σ⁻¹(μ − rf) = [0.0027, 0.0027] / det → 50/50
        weights = optimization.maximum_sharpe(market2(), 0.03)
        assert weights == pytest.approx([0.5, 0.5], abs=1e-6)

    def test_sharpe_is_not_beaten_by_random_portfolios(self) -> None:
        market = market3()
        best = optimization.describe(optimization.maximum_sharpe(market, 0.02), market, 0.02)
        rng = np.random.default_rng(11)
        for candidate in rng.dirichlet(np.ones(3), size=500):
            point = optimization.describe(candidate, market, 0.02)
            assert point.sharpe_ratio is not None and best.sharpe_ratio is not None
            assert point.sharpe_ratio <= best.sharpe_ratio + 1e-9

    def test_requires_expected_returns(self) -> None:
        with pytest.raises(InvalidInputError, match="expected_returns"):
            optimization.maximum_sharpe(market_from_covariance(COV2, None), 0.03)


class TestEfficientFrontier:
    def test_frontier_properties(self) -> None:
        market = market3()
        frontier = optimization.efficient_frontier(market, 8, risk_free_rate=0.02)
        returns = [float(point.expected_return or 0.0) for point in frontier]
        assert all(point.expected_return is not None for point in frontier)
        vols = [point.volatility for point in frontier]
        min_var = optimization.describe(optimization.minimum_variance(market), market)

        assert len(frontier) == 8
        assert returns == sorted(returns)
        assert vols == sorted(vols)
        assert vols[0] == pytest.approx(min_var.volatility, rel=1e-8)
        assert returns[-1] == pytest.approx(max(MU3))
        for point in frontier:
            assert point.weights.sum() == pytest.approx(1)

    def test_equal_expected_returns_collapse_to_one_point(self) -> None:
        market = market_from_covariance(COV2, [0.1, 0.1])
        assert len(optimization.efficient_frontier(market, 10)) == 1


class TestHeuristicPortfolios:
    def test_two_asset_risk_parity_is_inverse_volatility(self) -> None:
        weights = optimization.risk_parity(market2())
        assert weights == pytest.approx([0.6, 0.4], abs=1e-8)
        assert optimization.inverse_volatility(market2()) == pytest.approx([0.6, 0.4])

    def test_three_asset_risk_parity_equalizes_contributions(self) -> None:
        market = market3()
        weights = optimization.risk_parity(market)
        _, items = analytics.risk_contributions(weights, market.covariance)

        assert weights.sum() == pytest.approx(1)
        assert [item.percent_contribution for item in items] == pytest.approx([1 / 3] * 3, abs=1e-8)

    def test_risk_parity_rejects_zero_variance_asset(self) -> None:
        market = market_from_covariance([[0.0, 0.0], [0.0, 0.09]], None)
        with pytest.raises(InvalidInputError, match="positive variance"):
            optimization.risk_parity(market)

    def test_inverse_volatility_zero_volatility(self) -> None:
        market = market_from_covariance([[0.0, 0.0], [0.0, 0.09]], None)
        with pytest.raises(DivisionByZeroError):
            optimization.inverse_volatility(market)
