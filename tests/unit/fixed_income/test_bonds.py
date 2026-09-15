import math

import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.fixed_income import bonds
from app.services.fixed_income.bonds import BondTerms

ANNUAL_10 = BondTerms(face_value=1000, coupon_rate=0.10, years=3, frequency=1)
SEMI_6 = BondTerms(face_value=1000, coupon_rate=0.06, years=5, frequency=2)
ZERO = BondTerms(face_value=1000, coupon_rate=0.0, years=3, frequency=1)

SEMI_6_AT_8 = math.fsum(30 / 1.04**k for k in range(1, 11)) + 1000 / 1.04**10


class TestPricing:
    def test_par_bond(self) -> None:
        assert bonds.value_bond(ANNUAL_10, 0.10).price == pytest.approx(1000)

    def test_semiannual_discount_bond(self) -> None:
        valuation = bonds.value_bond(SEMI_6, 0.08)

        assert valuation.price == pytest.approx(SEMI_6_AT_8)
        assert valuation.price == pytest.approx(918.891042, rel=1e-9)
        assert valuation.periodic_yield == pytest.approx(0.04)
        assert len(valuation.cash_flows) == 10
        assert valuation.cash_flows[-1].cash_flow == pytest.approx(1030)
        assert valuation.cash_flows[-1].time_years == pytest.approx(5)

    def test_zero_coupon(self) -> None:
        assert bonds.value_bond(ZERO, 0.10).price == pytest.approx(1000 / 1.331)

    def test_negative_yield_prices_above_face(self) -> None:
        assert bonds.value_bond(SEMI_6, -0.01).price > 1000 + 60 * 5

    def test_non_whole_periods_are_invalid(self) -> None:
        terms = BondTerms(face_value=1000, coupon_rate=0.06, years=2.3, frequency=2)
        with pytest.raises(InvalidInputError, match="whole number"):
            bonds.value_bond(terms, 0.08)

    def test_yield_at_minus_frequency_is_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            bonds.value_bond(SEMI_6, -2.0)


class TestYields:
    def test_ytm_recovers_pricing_yield(self) -> None:
        result = bonds.yield_to_maturity(SEMI_6, SEMI_6_AT_8)

        assert result.annual_yield == pytest.approx(0.08, abs=1e-12)
        assert result.periodic_yield == pytest.approx(0.04, abs=1e-12)
        assert result.effective_annual_yield == pytest.approx(1.04**2 - 1, abs=1e-12)

    def test_ytm_of_par_bond_equals_coupon(self) -> None:
        assert bonds.yield_to_maturity(ANNUAL_10, 1000).annual_yield == pytest.approx(0.10)

    def test_ytm_of_zero_coupon(self) -> None:
        assert bonds.yield_to_maturity(ZERO, 1000 / 1.331).annual_yield == pytest.approx(0.10)

    def test_ytm_negative_yield_edge(self) -> None:
        price = bonds.value_bond(SEMI_6, -0.005).price
        assert bonds.yield_to_maturity(SEMI_6, price).annual_yield == pytest.approx(-0.005)

    def test_ytm_deep_discount_edge(self) -> None:
        price = bonds.value_bond(SEMI_6, 1.5).price
        assert bonds.yield_to_maturity(SEMI_6, price).annual_yield == pytest.approx(1.5)

    def test_ytm_invalid_price(self) -> None:
        with pytest.raises(InvalidInputError):
            bonds.yield_to_maturity(SEMI_6, 0)

    def test_ytc_round_trip(self) -> None:
        callable_bond = BondTerms(face_value=1000, coupon_rate=0.08, years=10, frequency=2)
        result = bonds.yield_to_call(callable_bond, 1100, 1040, 5)

        periodic = result.periodic_yield
        repriced = math.fsum(40 / (1 + periodic) ** k for k in range(1, 11))
        repriced += 1040 / (1 + periodic) ** 10
        assert repriced == pytest.approx(1100)

    def test_ytc_at_maturity_equals_ytm_when_call_price_is_face(self) -> None:
        ytc = bonds.yield_to_call(SEMI_6, SEMI_6_AT_8, 1000, 5).annual_yield
        assert ytc == pytest.approx(0.08)

    def test_ytc_after_maturity_is_invalid(self) -> None:
        with pytest.raises(InvalidInputError, match="years_to_call"):
            bonds.yield_to_call(SEMI_6, 1000, 1000, 6)

    def test_current_yield(self) -> None:
        assert bonds.current_yield(60, 918.89) == pytest.approx(60 / 918.89)

    def test_current_yield_zero_price(self) -> None:
        with pytest.raises(DivisionByZeroError):
            bonds.current_yield(60, 0)


class TestDuration:
    def test_textbook_annual_bond(self) -> None:
        result = bonds.duration_and_convexity(ANNUAL_10, 0.10)

        macaulay = (1 * 100 / 1.1 + 2 * 100 / 1.1**2 + 3 * 1100 / 1.1**3) / 1000
        convexity = (100 * 2 / 1.1**3 + 100 * 6 / 1.1**4 + 1100 * 12 / 1.1**5) / 1000
        assert result.macaulay_duration == pytest.approx(macaulay)
        assert result.macaulay_duration == pytest.approx(2.7355371900826446)
        assert result.modified_duration == pytest.approx(macaulay / 1.1)
        assert result.convexity == pytest.approx(convexity)

    def test_zero_coupon_macaulay_equals_maturity(self) -> None:
        result = bonds.duration_and_convexity(ZERO, 0.07)
        assert result.macaulay_duration == pytest.approx(3)

    def test_semiannual_duration_in_years(self) -> None:
        result = bonds.duration_and_convexity(SEMI_6, 0.08)
        flows = [30.0] * 9 + [1030.0]
        pvs = [cf / 1.04**k for k, cf in enumerate(flows, start=1)]
        macaulay = math.fsum((k / 2) * pv for k, pv in enumerate(pvs, start=1)) / math.fsum(pvs)
        assert result.macaulay_duration == pytest.approx(macaulay)
        assert result.modified_duration == pytest.approx(macaulay / 1.04)

    def test_duration_predicts_small_price_change(self) -> None:
        result = bonds.duration_and_convexity(SEMI_6, 0.08)
        shock = 0.0001
        actual = bonds.value_bond(SEMI_6, 0.08 + shock).price / result.price - 1
        approximation = -result.modified_duration * shock + 0.5 * result.convexity * shock**2
        assert actual == pytest.approx(approximation, rel=1e-4)

    def test_spread(self) -> None:
        assert bonds.yield_spread(0.0825, 0.064) == pytest.approx(0.0185)
