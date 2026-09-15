import math

import pytest

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.services.fixed_income import interest, rates


class TestGrowthFactors:
    def test_simple(self) -> None:
        assert interest.simple_growth_factor(0.12, 2) == pytest.approx(1.24)

    def test_periodic_monthly(self) -> None:
        assert interest.periodic_growth_factor(0.12, 1, 12) == pytest.approx(1.01**12)

    def test_continuous(self) -> None:
        assert interest.continuous_growth_factor(0.12, 1) == pytest.approx(math.exp(0.12))

    def test_zero_time_is_neutral(self) -> None:
        assert interest.simple_growth_factor(0.12, 0) == 1
        assert interest.periodic_growth_factor(0.12, 0, 12) == 1
        assert interest.continuous_growth_factor(0.12, 0) == 1

    def test_periodic_converges_to_continuous(self) -> None:
        daily = interest.periodic_growth_factor(0.12, 1, 365)
        assert daily == pytest.approx(math.exp(0.12), rel=1e-4)

    def test_interest_amount(self) -> None:
        assert interest.interest_amount(1000, 1.24) == pytest.approx((240, 1240))

    def test_discount(self) -> None:
        assert interest.discount(1240, 1.24) == pytest.approx(1000)

    def test_discount_rejects_non_positive_factor(self) -> None:
        with pytest.raises(InvalidInputError):
            interest.discount(100, interest.simple_growth_factor(-1, 2))

    def test_periodic_rate_at_minus_frequency_is_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            interest.periodic_growth_factor(-12, 1, 12)

    def test_overflow(self) -> None:
        with pytest.raises(NonFiniteResultError):
            interest.continuous_growth_factor(1e6, 1e6)


class TestRates:
    def test_effective_from_nominal(self) -> None:
        assert rates.effective_from_nominal(0.12, 12) == pytest.approx(1.01**12 - 1)

    def test_effective_equals_nominal_with_annual_compounding(self) -> None:
        assert rates.effective_from_nominal(0.12, 1) == pytest.approx(0.12)

    def test_effective_from_continuous(self) -> None:
        assert rates.effective_from_continuous(0.12) == pytest.approx(math.exp(0.12) - 1)

    def test_nominal_round_trip(self) -> None:
        effective = rates.effective_from_nominal(0.12, 12)
        assert rates.nominal_from_effective(effective, 12) == pytest.approx(0.12)

    def test_nominal_from_effective_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            rates.nominal_from_effective(-1, 12)

    def test_real_rate_exact(self) -> None:
        assert rates.real_rate_exact(0.10, 0.04) == pytest.approx(1.10 / 1.04 - 1)

    def test_real_rate_with_deflation(self) -> None:
        assert rates.real_rate_exact(0.02, -0.01) == pytest.approx(1.02 / 0.99 - 1)

    def test_real_rate_approximate(self) -> None:
        assert rates.real_rate_approximate(0.10, 0.04) == pytest.approx(0.06)

    def test_real_rate_invalid_inflation(self) -> None:
        with pytest.raises(InvalidInputError):
            rates.real_rate_exact(0.10, -1)

    def test_convert_annual_to_business_day(self) -> None:
        assert rates.convert_effective_rate(0.1365, 1, 1 / 252) == pytest.approx(
            1.1365 ** (1 / 252) - 1
        )

    def test_convert_monthly_to_annual(self) -> None:
        assert rates.convert_effective_rate(0.01, 1 / 12, 1) == pytest.approx(1.01**12 - 1)

    def test_convert_same_period_is_identity(self) -> None:
        assert rates.convert_effective_rate(0.05, 0.5, 0.5) == pytest.approx(0.05)

    @pytest.mark.parametrize(("rate", "from_years", "to_years"), [(-1, 1, 1), (0.1, 0, 1)])
    def test_convert_invalid(self, rate: float, from_years: float, to_years: float) -> None:
        with pytest.raises(InvalidInputError):
            rates.convert_effective_rate(rate, from_years, to_years)
