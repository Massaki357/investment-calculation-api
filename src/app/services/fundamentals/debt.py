"""Indebtedness and solvency ratios."""

from app.utils.math import safe_divide


def gross_debt(
    short_term_debt: float, long_term_debt: float, lease_liabilities: float = 0
) -> float:
    """Gross Debt = short_term_debt + long_term_debt + lease_liabilities."""
    return short_term_debt + long_term_debt + lease_liabilities


def net_debt(
    gross_debt: float, cash_and_equivalents: float, short_term_investments: float = 0
) -> float:
    """Net Debt = gross_debt − cash_and_equivalents − short_term_investments.

    A negative value means a net cash position.
    """
    return gross_debt - cash_and_equivalents - short_term_investments


def net_debt_to_ebitda(net_debt: float, ebitda: float) -> float:
    """Net Debt/EBITDA = net_debt / ebitda."""
    return safe_divide(net_debt, ebitda, denominator_name="ebitda")


def debt_to_equity(gross_debt: float, shareholders_equity: float) -> float:
    """Debt/Equity = gross_debt / shareholders_equity."""
    return safe_divide(gross_debt, shareholders_equity, denominator_name="shareholders_equity")


def debt_to_capital(gross_debt: float, shareholders_equity: float) -> float:
    """Debt/Total Capital = gross_debt / (gross_debt + shareholders_equity)."""
    return safe_divide(
        gross_debt,
        gross_debt + shareholders_equity,
        denominator_name="total_capital (gross_debt + shareholders_equity)",
    )


def interest_coverage(ebit: float, interest_expense: float) -> float:
    """Interest Coverage = ebit / interest_expense."""
    return safe_divide(ebit, interest_expense, denominator_name="interest_expense")


def debt_to_free_cash_flow(gross_debt: float, free_cash_flow: float) -> float:
    """Debt/FCF = gross_debt / free_cash_flow."""
    return safe_divide(gross_debt, free_cash_flow, denominator_name="free_cash_flow")
