import pytest

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.services.valuation import time_value as tv


class TestPresentAndFutureValue:
    def test_present_value_known_value(self) -> None:
        assert tv.present_value(100, 0.10, 1) == pytest.approx(90.9090909090909)

    def test_future_value_known_value(self) -> None:
        # 1000 × 1.05^10
        assert tv.future_value(1000, 0.05, 10) == pytest.approx(1628.894626777442)

    def test_fractional_periods(self) -> None:
        assert tv.present_value(1000, 0.08, 2.5) == pytest.approx(1000 / 1.08**2.5)

    def test_zero_rate_keeps_value(self) -> None:
        assert tv.present_value(500, 0, 7) == 500
        assert tv.future_value(500, 0, 7) == 500

    def test_zero_periods_keeps_value(self) -> None:
        assert tv.future_value(1000, 0.05, 0) == 1000

    def test_negative_rate_above_minus_one(self) -> None:
        assert tv.present_value(100, -0.5, 1) == pytest.approx(200)

    def test_present_and_future_value_are_inverse(self) -> None:
        assert tv.present_value(tv.future_value(1000, 0.07, 12), 0.07, 12) == pytest.approx(1000)

    @pytest.mark.parametrize("rate", [-1.0, -1.5])
    def test_rate_at_or_below_minus_one_is_invalid(self, rate: float) -> None:
        with pytest.raises(InvalidInputError, match="greater than -1"):
            tv.future_value(100, rate, 1)

    def test_overflow_raises_non_finite(self) -> None:
        with pytest.raises(NonFiniteResultError):
            tv.future_value(1, 1e10, 1e10)


class TestDiscountCashFlows:
    def test_end_of_period_timing(self) -> None:
        result = tv.discount_cash_flows([100, 110, 121], 0.10)

        assert [item.period for item in result] == [1, 2, 3]
        assert [item.present_value for item in result] == pytest.approx([90.9090909090909] * 3)

    def test_mid_year_convention(self) -> None:
        result = tv.discount_cash_flows([100, 110], 0.10, mid_year_convention=True)

        assert [item.period for item in result] == [0.5, 1.5]
        assert result[0].discount_factor == pytest.approx(1 / 1.1**0.5)
        assert result[1].present_value == pytest.approx(110 / 1.1**1.5)

    def test_custom_periods(self) -> None:
        result = tv.discount_cash_flows([50, 50], 0.10, [0, 2])

        assert result[0].present_value == 50
        assert result[1].present_value == pytest.approx(50 / 1.21)

    def test_mismatched_periods_are_invalid(self) -> None:
        with pytest.raises(InvalidInputError, match="same length"):
            tv.discount_cash_flows([1, 2], 0.10, [1])

    def test_negative_period_is_invalid(self) -> None:
        with pytest.raises(InvalidInputError, match="negative"):
            tv.discount_cash_flows([1], 0.10, [-1])
