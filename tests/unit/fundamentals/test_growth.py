import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError, NonFiniteResultError
from app.services.fundamentals import growth as g


class TestGrowthRate:
    def test_known_value(self) -> None:
        assert g.growth_rate(1100, 1000) == pytest.approx(0.10)

    def test_decline(self) -> None:
        assert g.growth_rate(81, 90) == pytest.approx(-0.10)

    def test_negative_base_uses_absolute_value(self) -> None:
        assert g.growth_rate(-50, -100) == pytest.approx(0.50)

    def test_crossing_from_negative_to_positive(self) -> None:
        assert g.growth_rate(50, -100) == pytest.approx(1.50)

    def test_zero_previous_raises(self) -> None:
        with pytest.raises(DivisionByZeroError, match="previous_value"):
            g.growth_rate(100, 0)


class TestCagr:
    def test_doubling_in_five_years(self) -> None:
        # 2 ** (1/5) − 1
        assert g.cagr(100, 200, 5) == pytest.approx(0.148698354997035, rel=1e-12)

    def test_ten_percent_over_five_years(self) -> None:
        assert g.cagr(1.0, 1.61051, 5) == pytest.approx(0.10, rel=1e-12)

    def test_fractional_years(self) -> None:
        assert g.cagr(100, 121, 2) == pytest.approx(0.10)
        assert g.cagr(100, 110, 0.5) == pytest.approx(0.21)

    def test_no_change_is_zero(self) -> None:
        assert g.cagr(100, 100, 3) == 0

    @pytest.mark.parametrize(
        ("beginning", "ending", "years", "match"),
        [
            (0, 100, 5, "beginning_value"),
            (-100, 100, 5, "beginning_value"),
            (100, 0, 5, "ending_value"),
            (100, -50, 5, "ending_value"),
            (100, 200, 0, "years"),
        ],
    )
    def test_invalid_inputs(
        self, beginning: float, ending: float, years: float, match: str
    ) -> None:
        with pytest.raises(InvalidInputError, match=match):
            g.cagr(beginning, ending, years)

    def test_overflow_raises_non_finite(self) -> None:
        with pytest.raises(NonFiniteResultError):
            g.cagr(1e-300, 1e300, 0.001)


class TestReinvestmentMetrics:
    def test_sustainable_growth_rate(self) -> None:
        assert g.sustainable_growth_rate(0.18, 0.60) == pytest.approx(0.108)

    def test_sustainable_growth_with_full_payout_is_zero(self) -> None:
        assert g.sustainable_growth_rate(0.18, 0.0) == 0

    def test_retention_ratio(self) -> None:
        assert g.retention_ratio(200, 50) == pytest.approx(0.75)

    def test_retention_ratio_without_dividends_is_one(self) -> None:
        assert g.retention_ratio(200, 0) == 1

    def test_retention_ratio_zero_income_raises(self) -> None:
        with pytest.raises(DivisionByZeroError, match="net_income"):
            g.retention_ratio(0, 50)

    def test_reinvestment_rate(self) -> None:
        # (150 − 50 + 20) / (300 × 0.66) = 120 / 198
        assert g.reinvestment_rate(150, 50, 20, 300, 0.34) == pytest.approx(0.6060606060606061)

    def test_negative_net_investment(self) -> None:
        assert g.reinvestment_rate(40, 50, -10, 300, 0.34) == pytest.approx(-20 / 198)

    def test_reinvestment_rate_zero_nopat_raises(self) -> None:
        with pytest.raises(DivisionByZeroError, match="nopat"):
            g.reinvestment_rate(150, 50, 20, 300, 1.0)
