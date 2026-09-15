import pytest

from app.core.exceptions import InvalidInputError
from app.services.valuation import ddm


class TestSimpleModels:
    def test_ddm_with_terminal_price(self) -> None:
        expected = 2 / 1.1 + 2.1 / 1.1**2 + 2.2 / 1.1**3 + 40 / 1.1**3
        assert ddm.dividend_discount_model([2, 2.1, 2.2], 0.10, 40) == pytest.approx(expected)

    def test_ddm_without_terminal_price(self) -> None:
        assert ddm.dividend_discount_model([10], 0.25) == pytest.approx(8)

    def test_ddm_zero_dividends(self) -> None:
        assert ddm.dividend_discount_model([0, 0], 0.10) == 0

    def test_ddm_empty_dividends_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            ddm.dividend_discount_model([], 0.10)

    def test_gordon_known_value(self) -> None:
        # D1 = 2 × 1.05 = 2.1; 2.1 / (0.10 − 0.05)
        assert ddm.gordon_growth_value(2.1, 0.10, 0.05) == pytest.approx(42)

    def test_gordon_negative_growth(self) -> None:
        assert ddm.gordon_growth_value(2, 0.10, -0.02) == pytest.approx(2 / 0.12)

    def test_gordon_requires_rate_above_growth(self) -> None:
        with pytest.raises(InvalidInputError, match="greater than growth_rate"):
            ddm.gordon_growth_value(2, 0.05, 0.05)


class TestTwoStage:
    def test_known_value(self) -> None:
        # D1 = 1.1, D2 = 1.21 → PV = 1 + 1; P2 = 1.21 × 1.03 / 0.07; PV(P2) = P2 / 1.21
        result = ddm.two_stage_ddm(1.0, 0.10, 2, 0.03, 0.10)

        assert [p.dividend for p in result.projections] == pytest.approx([1.1, 1.21])
        assert result.present_value_of_dividends == pytest.approx(2.0)
        assert result.terminal_dividend == pytest.approx(1.21 * 1.03)
        assert result.terminal_value == pytest.approx(1.21 * 1.03 / 0.07)
        assert result.value == pytest.approx(2 + 1.03 / 0.07)
        assert result.terminal_value_percentage == pytest.approx((1.03 / 0.07) / (2 + 1.03 / 0.07))

    def test_stable_cost_of_equity_only_affects_terminal_price(self) -> None:
        result = ddm.two_stage_ddm(1.0, 0.10, 2, 0.03, 0.10, stable_cost_of_equity=0.08)

        assert result.present_value_of_dividends == pytest.approx(2.0)
        assert result.terminal_value == pytest.approx(1.21 * 1.03 / 0.05)
        assert result.value == pytest.approx(2 + 1.03 / 0.05)

    def test_equals_gordon_when_growth_is_constant(self) -> None:
        two_stage = ddm.two_stage_ddm(2.0, 0.05, 5, 0.05, 0.10).value
        assert two_stage == pytest.approx(ddm.gordon_growth_value(2.1, 0.10, 0.05))

    def test_zero_dividend_edge_case(self) -> None:
        result = ddm.two_stage_ddm(0.0, 0.10, 3, 0.03, 0.10)

        assert result.value == 0
        assert result.terminal_value_percentage is None

    def test_stable_rate_must_exceed_stable_growth(self) -> None:
        with pytest.raises(InvalidInputError, match="stable_growth_rate"):
            ddm.two_stage_ddm(1.0, 0.10, 2, 0.10, 0.10)

    def test_years_must_be_positive(self) -> None:
        with pytest.raises(InvalidInputError, match="high_growth_years"):
            ddm.two_stage_ddm(1.0, 0.10, 0, 0.03, 0.10)


class TestThreeStage:
    def test_known_value_with_linear_transition(self) -> None:
        result = ddm.three_stage_ddm(1.0, 0.10, 1, 2, 0.04, 0.10)

        growths = [p.growth_rate for p in result.projections]
        assert growths == pytest.approx([0.10, 0.07, 0.04])
        assert [p.stage for p in result.projections] == ["high_growth", "transition", "transition"]

        d1, d2, d3 = 1.1, 1.1 * 1.07, 1.1 * 1.07 * 1.04
        terminal = d3 * 1.04 / 0.06
        expected = d1 / 1.1 + d2 / 1.1**2 + d3 / 1.1**3 + terminal / 1.1**3
        assert result.terminal_value == pytest.approx(terminal)
        assert result.value == pytest.approx(expected)

    def test_single_transition_year_reaches_stable_growth_immediately(self) -> None:
        result = ddm.three_stage_ddm(1.0, 0.10, 2, 1, 0.04, 0.10)

        assert [p.growth_rate for p in result.projections] == pytest.approx([0.10, 0.10, 0.04])

    def test_transition_years_must_be_positive(self) -> None:
        with pytest.raises(InvalidInputError, match="transition_years"):
            ddm.three_stage_ddm(1.0, 0.10, 2, 0, 0.04, 0.10)
