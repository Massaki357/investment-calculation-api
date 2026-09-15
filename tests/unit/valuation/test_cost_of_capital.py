import pytest

from app.core.exceptions import DivisionByZeroError
from app.services.valuation import cost_of_capital as coc


class TestCapmAndBeta:
    def test_capm(self) -> None:
        assert coc.capm(0.04, 1.2, 0.055) == pytest.approx(0.106)

    def test_capm_zero_beta_is_risk_free(self) -> None:
        assert coc.capm(0.04, 0, 0.055) == pytest.approx(0.04)

    def test_market_risk_premium(self) -> None:
        assert coc.market_risk_premium(0.10, 0.04) == pytest.approx(0.06)

    def test_levered_beta(self) -> None:
        # 0.8 × (1 + 0.66 × 0.5)
        assert coc.levered_beta(0.8, 0.34, 0.5) == pytest.approx(1.064)

    def test_unlevered_beta(self) -> None:
        assert coc.unlevered_beta(1.064, 0.34, 0.5) == pytest.approx(0.8)

    def test_relevering_round_trip(self) -> None:
        levered = coc.levered_beta(0.75, 0.25, 1.3)
        assert coc.unlevered_beta(levered, 0.25, 1.3) == pytest.approx(0.75)

    def test_no_debt_leaves_beta_unchanged(self) -> None:
        assert coc.levered_beta(0.8, 0.34, 0) == 0.8
        assert coc.unlevered_beta(0.8, 0.34, 0) == 0.8

    def test_full_tax_rate_removes_leverage_effect(self) -> None:
        assert coc.levered_beta(0.8, 1.0, 2.0) == pytest.approx(0.8)


class TestCostOfEquityAndDebt:
    def test_cost_of_equity_with_premia(self) -> None:
        assert coc.cost_of_equity(0.04, 1.2, 0.055, 0.02, 0.01) == pytest.approx(0.136)

    def test_cost_of_equity_defaults_to_capm(self) -> None:
        assert coc.cost_of_equity(0.04, 1.2, 0.055) == coc.capm(0.04, 1.2, 0.055)

    def test_cost_of_debt_from_spread(self) -> None:
        assert coc.cost_of_debt_from_spread(0.04, 0.02) == pytest.approx(0.06)

    def test_cost_of_debt_from_interest(self) -> None:
        assert coc.cost_of_debt_from_interest(45, 500) == pytest.approx(0.09)

    def test_cost_of_debt_zero_debt_raises(self) -> None:
        with pytest.raises(DivisionByZeroError, match="total_debt"):
            coc.cost_of_debt_from_interest(45, 0)

    def test_after_tax_cost_of_debt(self) -> None:
        assert coc.after_tax_cost_of_debt(0.08, 0.34) == pytest.approx(0.0528)

    def test_after_tax_cost_without_taxes(self) -> None:
        assert coc.after_tax_cost_of_debt(0.08, 0) == 0.08


class TestWacc:
    def test_known_value(self) -> None:
        result = coc.wacc(600, 400, 0.12, 0.08, 0.34)

        # 0.6 × 0.12 + 0.4 × 0.08 × 0.66
        assert result.wacc == pytest.approx(0.09312)
        assert result.equity_weight == pytest.approx(0.6)
        assert result.debt_weight == pytest.approx(0.4)
        assert result.after_tax_cost_of_debt == pytest.approx(0.0528)

    def test_all_equity_firm(self) -> None:
        assert coc.wacc(1000, 0, 0.12, 0.08, 0.34).wacc == pytest.approx(0.12)

    def test_zero_capital_raises(self) -> None:
        with pytest.raises(DivisionByZeroError, match="total_capital"):
            coc.wacc(0, 0, 0.12, 0.08, 0.34)
