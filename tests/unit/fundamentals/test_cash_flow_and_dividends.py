import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.fundamentals import cash_flow as cf
from app.services.fundamentals import dividends as dv


class TestCashFlow:
    def test_free_cash_flow(self) -> None:
        assert cf.free_cash_flow(500, 200) == 300

    def test_negative_free_cash_flow(self) -> None:
        assert cf.free_cash_flow(100, 200) == -100

    def test_fcff(self) -> None:
        # 300 × 0.66 + 50 − 150 − 20 = 78
        assert cf.free_cash_flow_to_firm(300, 0.34, 50, 150, 20) == pytest.approx(78.0)

    def test_fcff_without_taxes(self) -> None:
        assert cf.free_cash_flow_to_firm(300, 0, 50, 150, 20) == 180

    def test_fcff_working_capital_release_adds_cash(self) -> None:
        assert cf.free_cash_flow_to_firm(300, 0, 50, 150, -20) == 220

    def test_fcfe(self) -> None:
        # 78 − 40 × 0.66 + 30 = 81.6
        assert cf.free_cash_flow_to_equity(78, 40, 0.34, 30) == pytest.approx(81.6)

    def test_fcfe_with_net_repayment(self) -> None:
        assert cf.free_cash_flow_to_equity(78, 40, 0.34, -50) == pytest.approx(1.6)

    def test_ratios(self) -> None:
        assert cf.fcf_conversion(90, 120) == pytest.approx(0.75)
        assert cf.cash_conversion_ratio(150, 120) == pytest.approx(1.25)
        assert cf.cfo_margin(150, 1000) == pytest.approx(0.15)
        assert cf.capex_to_revenue(60, 1000) == pytest.approx(0.06)
        assert cf.capex_to_depreciation(60, 40) == pytest.approx(1.5)
        assert cf.cash_flow_per_share(150, 50) == pytest.approx(3.0)

    def test_negative_net_income_conversion(self) -> None:
        assert cf.fcf_conversion(90, -120) == pytest.approx(-0.75)

    def test_owner_earnings(self) -> None:
        assert cf.owner_earnings(120, 40, 30, 10) == 120

    def test_owner_earnings_with_working_capital_release(self) -> None:
        assert cf.owner_earnings(120, 40, 30, -10) == 140

    @pytest.mark.parametrize(
        ("func", "args", "field"),
        [
            (cf.fcf_conversion, (90, 0), "net_income"),
            (cf.cash_conversion_ratio, (150, 0), "net_income"),
            (cf.cfo_margin, (150, 0), "revenue"),
            (cf.capex_to_revenue, (60, 0), "revenue"),
            (cf.capex_to_depreciation, (60, 0), "depreciation_amortization"),
            (cf.cash_flow_per_share, (150, 0), "shares_outstanding"),
        ],
    )
    def test_zero_denominator_raises(self, func, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            func(*args)


class TestDividends:
    def test_dividend_yield(self) -> None:
        assert dv.dividend_yield(2.10, 35.0) == pytest.approx(0.06)

    def test_zero_dividend_yield(self) -> None:
        assert dv.dividend_yield(0, 35.0) == 0

    def test_payout(self) -> None:
        assert dv.dividend_payout_ratio(60, 120) == pytest.approx(0.5)

    def test_payout_with_loss_is_signed(self) -> None:
        assert dv.dividend_payout_ratio(60, -120) == pytest.approx(-0.5)

    def test_coverage(self) -> None:
        assert dv.dividend_coverage(4.20, 2.10) == pytest.approx(2.0)

    def test_dividend_cagr(self) -> None:
        assert dv.dividend_cagr(1.00, 1.61051, 5) == pytest.approx(0.10, rel=1e-12)

    def test_dividend_cagr_invalid_names_dividend_field(self) -> None:
        with pytest.raises(InvalidInputError, match="beginning_dividend"):
            dv.dividend_cagr(0, 1.61051, 5)

    def test_dividend_per_share(self) -> None:
        assert dv.dividend_per_share(60_000_000, 50_000_000) == pytest.approx(1.2)

    def test_yield_on_cost(self) -> None:
        assert dv.yield_on_cost(2.10, 15.0) == pytest.approx(0.14)

    @pytest.mark.parametrize(
        ("func", "args", "field"),
        [
            (dv.dividend_yield, (2.10, 0), "share_price"),
            (dv.dividend_payout_ratio, (60, 0), "net_income"),
            (dv.dividend_coverage, (4.20, 0), "dividend_per_share"),
            (dv.dividend_per_share, (60, 0), "shares_outstanding"),
            (dv.yield_on_cost, (2.10, 0), "average_cost_per_share"),
        ],
    )
    def test_zero_denominator_raises(self, func, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            func(*args)
