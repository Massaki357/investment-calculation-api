import pytest

from app.core.exceptions import DivisionByZeroError, InvalidInputError
from app.services.fundamentals import debt as d
from app.services.fundamentals import liquidity as liq


class TestDebt:
    def test_gross_debt(self) -> None:
        assert d.gross_debt(200, 800, 100) == 1100

    def test_gross_debt_without_leases(self) -> None:
        assert d.gross_debt(200, 800) == 1000

    def test_net_debt(self) -> None:
        assert d.net_debt(1100, 300, 100) == 700

    def test_net_cash_position_is_negative(self) -> None:
        assert d.net_debt(100, 300) == -200

    def test_net_debt_to_ebitda(self) -> None:
        assert d.net_debt_to_ebitda(700, 350) == pytest.approx(2.0)

    def test_net_cash_to_ebitda(self) -> None:
        assert d.net_debt_to_ebitda(-200, 350) == pytest.approx(-0.5714285714285714)

    def test_debt_to_equity(self) -> None:
        assert d.debt_to_equity(1100, 2200) == pytest.approx(0.5)

    def test_debt_to_negative_equity(self) -> None:
        assert d.debt_to_equity(1100, -1100) == pytest.approx(-1.0)

    def test_debt_to_capital(self) -> None:
        assert d.debt_to_capital(1100, 2200) == pytest.approx(1 / 3)

    def test_debt_free_company_has_zero_debt_to_capital(self) -> None:
        assert d.debt_to_capital(0, 2200) == 0

    def test_interest_coverage(self) -> None:
        assert d.interest_coverage(300, 60) == pytest.approx(5.0)

    def test_negative_ebit_coverage(self) -> None:
        assert d.interest_coverage(-30, 60) == pytest.approx(-0.5)

    def test_debt_to_fcf(self) -> None:
        assert d.debt_to_free_cash_flow(1100, 220) == pytest.approx(5.0)

    @pytest.mark.parametrize(
        ("func", "args", "field"),
        [
            (d.net_debt_to_ebitda, (700, 0), "ebitda"),
            (d.debt_to_equity, (1100, 0), "shareholders_equity"),
            (d.debt_to_capital, (0, 0), "total_capital"),
            (d.interest_coverage, (300, 0), "interest_expense"),
            (d.debt_to_free_cash_flow, (1100, 0), "free_cash_flow"),
        ],
    )
    def test_zero_denominator_raises(self, func, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            func(*args)


class TestLiquidity:
    def test_current_ratio(self) -> None:
        assert liq.current_ratio(1500, 1000) == pytest.approx(1.5)

    def test_current_ratio_without_assets(self) -> None:
        assert liq.current_ratio(0, 1000) == 0

    def test_quick_ratio(self) -> None:
        assert liq.quick_ratio(1500, 500, 1000) == pytest.approx(1.0)

    def test_quick_ratio_without_inventories_equals_current(self) -> None:
        assert liq.quick_ratio(1500, 0, 1000) == liq.current_ratio(1500, 1000)

    def test_quick_ratio_inventories_above_current_assets_raises(self) -> None:
        with pytest.raises(InvalidInputError, match="inventories"):
            liq.quick_ratio(400, 500, 1000)

    def test_cash_ratio(self) -> None:
        assert liq.cash_ratio(300, 1000, 100) == pytest.approx(0.4)

    def test_cash_ratio_without_investments(self) -> None:
        assert liq.cash_ratio(300, 1000) == pytest.approx(0.3)

    def test_general_liquidity(self) -> None:
        assert liq.general_liquidity_ratio(1500, 500, 1000, 1500) == pytest.approx(0.8)

    @pytest.mark.parametrize(
        ("func", "args", "field"),
        [
            (liq.current_ratio, (1500, 0), "current_liabilities"),
            (liq.quick_ratio, (1500, 500, 0), "current_liabilities"),
            (liq.cash_ratio, (300, 0), "current_liabilities"),
            (liq.general_liquidity_ratio, (1500, 500, 0, 0), "total_liabilities"),
        ],
    )
    def test_zero_denominator_raises(self, func, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            func(*args)
