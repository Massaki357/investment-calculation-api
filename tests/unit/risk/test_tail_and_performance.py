import math

import numpy as np
import pytest
from scipy import stats

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.risk import performance as perf
from app.services.risk import tail
from app.services.risk.returns import ReturnType

SIMPLE = ReturnType.SIMPLE
LADDER = [-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
BENCH = [0.010, -0.006, 0.011, -0.018, 0.007, 0.005, -0.010, 0.014, 0.006, -0.004]
ASSET = [0.012, -0.008, 0.015, -0.021, 0.009, 0.004, -0.013, 0.018, 0.007, -0.005]


class TestTailRisk:
    def test_historical_known_value(self) -> None:
        result = tail.historical_tail_risk(LADDER, confidence=0.90)

        # linear quantile at 10%: h = 9 × 0.1 = 0.9 → −0.05 + 0.9 × 0.02 = −0.032
        assert result.value_at_risk == pytest.approx(0.032)
        assert result.value_at_risk == pytest.approx(-np.quantile(LADDER, 0.10))
        assert result.expected_shortfall == pytest.approx(0.05)

    def test_historical_horizon_scaling(self) -> None:
        one = tail.historical_tail_risk(LADDER, 0.90, 1)
        four = tail.historical_tail_risk(LADDER, 0.90, 4)
        assert four.value_at_risk == pytest.approx(2 * one.value_at_risk)

    def test_parametric_matches_normal_formula(self) -> None:
        result = tail.parametric_tail_risk(ASSET, 0.95)
        mu, sigma = np.mean(ASSET), np.std(ASSET, ddof=1)
        z = 1.6448536269514722

        assert result.value_at_risk == pytest.approx(-(mu - z * sigma))
        assert result.expected_shortfall == pytest.approx(-(mu - sigma * stats.norm.pdf(z) / 0.05))

    def test_parametric_standard_normal_multipliers_without_mean(self) -> None:
        returns = [-0.02, 0.02]
        sigma = np.std(returns, ddof=1)
        result = tail.parametric_tail_risk(returns, 0.95, include_mean=False)

        assert result.value_at_risk / sigma == pytest.approx(1.6448536269514722)
        assert result.expected_shortfall / sigma == pytest.approx(2.0627128075074257)

    def test_shortfall_exceeds_var(self) -> None:
        result = tail.historical_tail_risk(ASSET, 0.9)
        assert result.expected_shortfall >= result.value_at_risk

    def test_invalid_confidence(self) -> None:
        with pytest.raises(InvalidInputError):
            tail.historical_tail_risk(LADDER, 1.5)


class TestMarketSensitivity:
    def test_beta_of_scaled_benchmark(self) -> None:
        asset = [2 * b + 0.001 for b in BENCH]
        assert perf.beta(asset, BENCH) == pytest.approx(2.0)

    def test_beta_constant_benchmark(self) -> None:
        with pytest.raises(DivisionByZeroError):
            perf.beta(ASSET, [0.01] * len(ASSET))

    def test_regression_alpha_recovers_intercept(self) -> None:
        asset = [0.0002 + 1.5 * b for b in BENCH]
        result = perf.regression_alpha(asset, BENCH, 0.0, 252, SIMPLE)

        assert result.periodic_alpha == pytest.approx(0.0002)
        assert result.annualized_alpha == pytest.approx(0.0002 * 252)
        assert result.beta == pytest.approx(1.5)


class TestRiskAdjusted:
    def test_downside_deviation_uses_all_observations(self) -> None:
        result = perf.downside_deviation([0.02, -0.01, 0.03, -0.02], 0.0, 252, SIMPLE)
        assert result == pytest.approx(math.sqrt((0.01**2 + 0.02**2) / 4))

    def test_sharpe_matches_manual(self) -> None:
        rf = 1.05 ** (1 / 252) - 1
        excess = np.array(ASSET) - rf
        expected = excess.mean() / excess.std(ddof=1) * math.sqrt(252)
        assert perf.sharpe_ratio(ASSET, 0.05, 252, SIMPLE) == pytest.approx(expected)

    def test_sharpe_zero_volatility(self) -> None:
        with pytest.raises(DivisionByZeroError):
            perf.sharpe_ratio([0.01, 0.01, 0.01], 0.0, 252, SIMPLE)

    def test_sortino_matches_manual(self) -> None:
        data = np.array(ASSET)
        downside = math.sqrt(np.mean(np.minimum(data, 0) ** 2))
        expected = data.mean() / downside * math.sqrt(252)
        assert perf.sortino_ratio(ASSET, 0.0, 252, SIMPLE) == pytest.approx(expected)

    def test_sortino_without_downside(self) -> None:
        with pytest.raises(DivisionByZeroError, match="downside"):
            perf.sortino_ratio([0.01, 0.02], 0.0, 252, SIMPLE)

    def test_treynor(self) -> None:
        annual = np.prod(1 + np.array(ASSET)) ** (252 / len(ASSET)) - 1
        expected = (annual - 0.05) / perf.beta(ASSET, BENCH)
        assert perf.treynor_ratio(ASSET, BENCH, 0.05, 252, SIMPLE) == pytest.approx(expected)

    def test_calmar_known_value(self) -> None:
        # wealth 1 → 1.1 → 0.88 → 1.144; MDD = −20%
        expected = (1.144 ** (1 / 3) - 1) / 0.2
        assert perf.calmar_ratio([0.1, -0.2, 0.3], 1, SIMPLE) == pytest.approx(expected)

    def test_calmar_without_drawdown(self) -> None:
        with pytest.raises(DivisionByZeroError):
            perf.calmar_ratio([0.01, 0.02], 252, SIMPLE)

    def test_information_ratio(self) -> None:
        active = np.array(ASSET) - np.array(BENCH)
        result = perf.information_ratio(ASSET, BENCH, 252, SIMPLE)

        assert result.tracking_error == pytest.approx(active.std(ddof=1) * math.sqrt(252))
        assert result.information_ratio == pytest.approx(
            active.mean() / active.std(ddof=1) * math.sqrt(252)
        )

    def test_jensens_alpha(self) -> None:
        result = perf.jensens_alpha(ASSET, BENCH, 0.05, 252, SIMPLE)
        expected = result.asset_return - (0.05 + result.beta * (result.benchmark_return - 0.05))
        assert result.alpha == pytest.approx(expected)

    def test_jensens_alpha_is_zero_for_the_benchmark_itself(self) -> None:
        assert perf.jensens_alpha(BENCH, BENCH, 0.05, 252, SIMPLE).alpha == pytest.approx(
            0, abs=1e-12
        )

    def test_m2_scales_sharpe_by_benchmark_volatility(self) -> None:
        result = perf.modigliani_m2(ASSET, BENCH, 0.05, 252, SIMPLE)
        sigma_m = np.std(BENCH, ddof=1) * math.sqrt(252)
        assert result.m2 == pytest.approx(result.sharpe_ratio * sigma_m + 0.05)

    def test_paired_length_mismatch(self) -> None:
        with pytest.raises(InvalidInputError, match="same length"):
            perf.information_ratio(ASSET, BENCH[:-1], 252, SIMPLE)
