"""Cost of capital: CAPM, beta relevering, cost of equity and debt, WACC."""

from dataclasses import dataclass

from app.utils.math import safe_divide
from app.utils.validation import ensure_finite


def market_risk_premium(expected_market_return: float, risk_free_rate: float) -> float:
    """Market Risk Premium = expected_market_return − risk_free_rate."""
    return expected_market_return - risk_free_rate


def capm(risk_free_rate: float, beta: float, market_risk_premium: float) -> float:
    """CAPM: E(R) = risk_free_rate + beta × market_risk_premium."""
    return ensure_finite(risk_free_rate + beta * market_risk_premium, "expected return")


def levered_beta(unlevered_beta: float, tax_rate: float, debt_to_equity: float) -> float:
    """Hamada: βL = βU × [1 + (1 − tax_rate) × D/E]."""
    return ensure_finite(unlevered_beta * (1 + (1 - tax_rate) * debt_to_equity), "levered beta")


def unlevered_beta(levered_beta: float, tax_rate: float, debt_to_equity: float) -> float:
    """Hamada: βU = βL / [1 + (1 − tax_rate) × D/E]."""
    return safe_divide(
        levered_beta,
        1 + (1 - tax_rate) * debt_to_equity,
        denominator_name="leverage factor (1 + (1 - tax_rate) × debt_to_equity)",
    )


def cost_of_equity(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
    country_risk_premium: float = 0,
    size_premium: float = 0,
    specific_risk_premium: float = 0,
) -> float:
    """Ke = rf + β × MRP + country_risk_premium + size_premium + specific_risk_premium."""
    return ensure_finite(
        capm(risk_free_rate, beta, market_risk_premium)
        + country_risk_premium
        + size_premium
        + specific_risk_premium,
        "cost of equity",
    )


def cost_of_debt_from_spread(risk_free_rate: float, credit_spread: float) -> float:
    """Kd (pre-tax) = risk_free_rate + credit_spread."""
    return risk_free_rate + credit_spread


def cost_of_debt_from_interest(interest_expense: float, total_debt: float) -> float:
    """Kd (pre-tax) = interest_expense / total_debt (average debt recommended)."""
    return safe_divide(interest_expense, total_debt, denominator_name="total_debt")


def after_tax_cost_of_debt(pre_tax_cost_of_debt: float, tax_rate: float) -> float:
    """Kd (after tax) = pre_tax_cost_of_debt × (1 − tax_rate)."""
    return pre_tax_cost_of_debt * (1 - tax_rate)


@dataclass(frozen=True, slots=True)
class WaccResult:
    wacc: float
    equity_weight: float
    debt_weight: float
    after_tax_cost_of_debt: float


def wacc(
    equity_value: float,
    debt_value: float,
    cost_of_equity: float,
    pre_tax_cost_of_debt: float,
    tax_rate: float,
) -> WaccResult:
    """WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1 − tax_rate)."""
    total_capital = equity_value + debt_value
    equity_weight = safe_divide(
        equity_value, total_capital, denominator_name="total_capital (equity_value + debt_value)"
    )
    debt_weight = safe_divide(
        debt_value, total_capital, denominator_name="total_capital (equity_value + debt_value)"
    )
    kd_after_tax = after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate)
    return WaccResult(
        wacc=ensure_finite(equity_weight * cost_of_equity + debt_weight * kd_after_tax, "WACC"),
        equity_weight=equity_weight,
        debt_weight=debt_weight,
        after_tax_cost_of_debt=kd_after_tax,
    )
