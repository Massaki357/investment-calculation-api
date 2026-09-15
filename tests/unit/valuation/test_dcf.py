import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.valuation import dcf


class TestTerminalValue:
    def test_perpetuity_growth_known_value(self) -> None:
        # 121 × 1.02 / (0.10 − 0.02)
        assert dcf.perpetuity_growth_terminal_value(121, 0.10, 0.02) == pytest.approx(1542.75)

    def test_zero_growth_is_a_plain_perpetuity(self) -> None:
        assert dcf.perpetuity_growth_terminal_value(121, 0.10, 0) == pytest.approx(1210)

    def test_negative_growth(self) -> None:
        assert dcf.perpetuity_growth_terminal_value(100, 0.10, -0.05) == pytest.approx(95 / 0.15)

    @pytest.mark.parametrize(("rate", "growth"), [(0.05, 0.05), (0.03, 0.05)])
    def test_discount_rate_must_exceed_growth(self, rate: float, growth: float) -> None:
        with pytest.raises(InvalidInputError, match="greater than growth_rate"):
            dcf.perpetuity_growth_terminal_value(100, rate, growth)

    def test_exit_multiple(self) -> None:
        assert dcf.exit_multiple_terminal_value(250, 8) == 2000

    def test_exit_multiple_negative_metric(self) -> None:
        assert dcf.exit_multiple_terminal_value(-50, 8) == -400


class TestValueBridge:
    def test_enterprise_value(self) -> None:
        assert dcf.enterprise_value(272.73, 1159.09) == pytest.approx(1431.82)

    def test_equity_value_full_bridge(self) -> None:
        assert dcf.equity_value(1431.82, 300, 50, 20) == pytest.approx(1101.82)

    def test_equity_value_with_net_cash(self) -> None:
        assert dcf.equity_value(1000, -200) == 1200

    def test_value_per_share(self) -> None:
        assert dcf.value_per_share(1101.82, 100) == pytest.approx(11.0182)

    def test_value_per_share_zero_shares(self) -> None:
        with pytest.raises(DivisionByZeroError, match="shares_outstanding"):
            dcf.value_per_share(1000, 0)

    def test_margin_of_safety(self) -> None:
        assert dcf.margin_of_safety(50, 35) == pytest.approx(0.3)

    def test_negative_margin_when_price_exceeds_value(self) -> None:
        assert dcf.margin_of_safety(50, 60) == pytest.approx(-0.2)

    @pytest.mark.parametrize("intrinsic", [0.0, -10.0])
    def test_margin_of_safety_requires_positive_intrinsic_value(self, intrinsic: float) -> None:
        with pytest.raises(InvalidInputError, match="intrinsic_value"):
            dcf.margin_of_safety(intrinsic, 35)


class TestDiscountedValuation:
    def test_known_values(self) -> None:
        result = dcf.discounted_valuation([100, 110, 121], 0.10, 1542.75)

        assert result.present_value_of_cash_flows == pytest.approx(3 * 100 / 1.1)
        assert result.terminal_discount_factor == pytest.approx(1 / 1.331)
        assert result.present_value_of_terminal_value == pytest.approx(1542.75 / 1.331)
        assert result.total_value == pytest.approx(3 * 100 / 1.1 + 1542.75 / 1.331)
        assert result.terminal_value_percentage == pytest.approx(
            (1542.75 / 1.331) / (3 * 100 / 1.1 + 1542.75 / 1.331)
        )

    def test_mid_year_only_shifts_explicit_cash_flows(self) -> None:
        result = dcf.discounted_valuation([100, 110, 121], 0.10, 1542.75, mid_year_convention=True)

        expected_pv = 100 / 1.1**0.5 + 110 / 1.1**1.5 + 121 / 1.1**2.5
        assert result.present_value_of_cash_flows == pytest.approx(expected_pv)
        assert result.present_value_of_terminal_value == pytest.approx(1542.75 / 1.331)

    def test_zero_total_value_has_no_terminal_percentage(self) -> None:
        result = dcf.discounted_valuation([-100], 0, 100)

        assert result.total_value == 0
        assert result.terminal_value_percentage is None

    def test_empty_cash_flows_are_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            dcf.discounted_valuation([], 0.10, 100)
