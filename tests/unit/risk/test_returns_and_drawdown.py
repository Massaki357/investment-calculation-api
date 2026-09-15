import math

import pytest

from app.core.exceptions import InvalidInputError
from app.services.risk import drawdown
from app.services.risk import returns as rt
from app.services.risk.returns import ReturnType

SIMPLE, LOG = ReturnType.SIMPLE, ReturnType.LOG


class TestReturns:
    def test_simple_returns_from_prices(self) -> None:
        assert rt.returns_from_prices([100, 110, 99], SIMPLE) == pytest.approx([0.1, -0.1])

    def test_log_returns_from_prices(self) -> None:
        assert rt.returns_from_prices([100, 110, 99], LOG) == pytest.approx(
            [math.log(1.1), math.log(0.9)]
        )

    def test_non_positive_price_is_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            rt.returns_from_prices([100, 0, 99], SIMPLE)

    def test_cumulative_return_simple_and_log_agree(self) -> None:
        simple = rt.cumulative_return([0.1, -0.1], SIMPLE)
        log = rt.cumulative_return([math.log(1.1), math.log(0.9)], LOG)
        assert simple == pytest.approx(-0.01)
        assert log == pytest.approx(-0.01)

    def test_cumulative_return_equals_price_ratio(self) -> None:
        prices = [100, 104, 97, 108]
        assert rt.cumulative_return(rt.returns_from_prices(prices, SIMPLE), SIMPLE) == (
            pytest.approx(108 / 100 - 1)
        )

    def test_annualized_return_of_twelve_monthly_returns(self) -> None:
        assert rt.annualized_return([0.01] * 12, SIMPLE, 12) == pytest.approx(1.01**12 - 1)

    def test_annualized_return_of_half_year(self) -> None:
        assert rt.annualized_return([0.01] * 6, SIMPLE, 12) == pytest.approx(1.01**12 - 1)

    def test_loss_of_100_percent_is_invalid_for_simple_returns(self) -> None:
        with pytest.raises(InvalidInputError):
            rt.cumulative_return([0.1, -1.0], SIMPLE)

    def test_periodic_rate(self) -> None:
        assert rt.periodic_rate(0.05, 252, SIMPLE) == pytest.approx(1.05 ** (1 / 252) - 1)
        assert rt.periodic_rate(0.05, 252, LOG) == pytest.approx(math.log(1.05) / 252)

    def test_periodic_rate_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            rt.periodic_rate(-1, 252, SIMPLE)

    def test_annualize_dispersion(self) -> None:
        assert rt.annualize_dispersion(0.01, 252) == pytest.approx(0.01 * math.sqrt(252))


class TestDrawdown:
    def test_worst_of_two_drawdowns(self) -> None:
        result = drawdown.maximum_drawdown([100, 120, 90, 95, 130, 80, 85])

        assert result.max_drawdown == pytest.approx(80 / 130 - 1)
        assert (result.peak_index, result.trough_index) == (4, 5)
        assert result.recovery_index is None
        assert result.duration_periods == 1

    def test_recovery(self) -> None:
        result = drawdown.maximum_drawdown([100, 80, 90, 100, 105])

        assert result.max_drawdown == pytest.approx(-0.2)
        assert (result.peak_index, result.trough_index, result.recovery_index) == (0, 1, 3)

    def test_no_drawdown_edge(self) -> None:
        result = drawdown.maximum_drawdown([100, 101, 102])

        assert result.max_drawdown == 0
        assert result.peak_index is None
        assert result.duration_periods is None

    def test_invalid_path(self) -> None:
        with pytest.raises(InvalidInputError):
            drawdown.maximum_drawdown([100, -5])
