import pytest

from app.core.exceptions import DivisionByZeroError
from app.services.fundamentals import profitability as p
from app.services.fundamentals.balances import average_balance


class TestKnownValues:
    def test_roe(self) -> None:
        assert p.return_on_equity(180, 1000) == pytest.approx(0.18)

    def test_roa(self) -> None:
        assert p.return_on_assets(180, 2400) == pytest.approx(0.075)

    def test_nopat(self) -> None:
        assert p.nopat(300, 0.34) == pytest.approx(198.0)

    def test_invested_capital(self) -> None:
        assert p.invested_capital(500, 1000, 300) == 1200

    def test_roic(self) -> None:
        assert p.return_on_invested_capital(300, 0.34, 1200) == pytest.approx(0.165)

    def test_roce(self) -> None:
        assert p.return_on_capital_employed(300, 2400, 400) == pytest.approx(0.15)

    @pytest.mark.parametrize(("numerator", "expected"), [(400, 0.4), (250, 0.25), (90, 0.09)])
    def test_margin(self, numerator: float, expected: float) -> None:
        assert p.margin(numerator, 1000) == pytest.approx(expected)

    def test_asset_turnover(self) -> None:
        assert p.asset_turnover(1000, 2000) == pytest.approx(0.5)

    def test_average_balance(self) -> None:
        assert average_balance(900, 1100) == 1000


class TestEdgeCases:
    def test_negative_net_income_gives_negative_roa(self) -> None:
        assert p.return_on_assets(-60, 2400) == pytest.approx(-0.025)

    def test_negative_equity_gives_signed_roe(self) -> None:
        assert p.return_on_equity(100, -500) == pytest.approx(-0.2)

    def test_zero_tax_rate_makes_nopat_equal_ebit(self) -> None:
        assert p.nopat(300, 0) == 300

    def test_full_tax_rate_makes_roic_zero(self) -> None:
        assert p.return_on_invested_capital(300, 1.0, 1200) == 0

    def test_negative_margin(self) -> None:
        assert p.margin(-50, 1000) == pytest.approx(-0.05)


class TestInvalidInputs:
    @pytest.mark.parametrize(
        ("func", "args", "field"),
        [
            (p.return_on_equity, (180, 0), "shareholders_equity"),
            (p.return_on_assets, (180, 0), "total_assets"),
            (p.return_on_invested_capital, (300, 0.34, 0), "invested_capital"),
            (p.return_on_capital_employed, (300, 400, 400), "capital_employed"),
            (p.margin, (100, 0), "revenue"),
            (p.asset_turnover, (1000, 0), "total_assets"),
        ],
    )
    def test_zero_denominator_raises(self, func, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            func(*args)


class TestDuPont:
    def test_three_factor_known_values(self) -> None:
        result = p.dupont_three_factor(120, 1000, 2000, 800)

        assert result.net_profit_margin == pytest.approx(0.12)
        assert result.asset_turnover == pytest.approx(0.5)
        assert result.equity_multiplier == pytest.approx(2.5)
        assert result.return_on_equity == pytest.approx(0.15)

    def test_five_factor_known_values(self) -> None:
        result = p.dupont_five_factor(120, 160, 200, 1000, 2000, 800)

        assert result.tax_burden == pytest.approx(0.75)
        assert result.interest_burden == pytest.approx(0.8)
        assert result.operating_margin == pytest.approx(0.2)
        assert result.asset_turnover == pytest.approx(0.5)
        assert result.equity_multiplier == pytest.approx(2.5)
        assert result.return_on_equity == pytest.approx(0.15)

    def test_both_decompositions_reconcile_to_direct_roe(self) -> None:
        direct = p.return_on_equity(120, 800)

        assert p.dupont_three_factor(120, 1000, 2000, 800).return_on_equity == pytest.approx(direct)
        assert p.dupont_five_factor(120, 160, 200, 1000, 2000, 800).return_on_equity == (
            pytest.approx(direct)
        )

    def test_negative_equity_edge_case(self) -> None:
        assert p.dupont_three_factor(120, 1000, 2000, -800).return_on_equity == pytest.approx(-0.15)

    @pytest.mark.parametrize(
        ("args", "field"),
        [
            ((120, 0, 200, 1000, 2000, 800), "pretax_income"),
            ((120, 160, 0, 1000, 2000, 800), "ebit"),
            ((120, 160, 200, 0, 2000, 800), "revenue"),
            ((120, 160, 200, 1000, 2000, 0), "shareholders_equity"),
        ],
    )
    def test_five_factor_zero_denominators(self, args, field: str) -> None:
        with pytest.raises(DivisionByZeroError, match=field):
            p.dupont_five_factor(*args)
