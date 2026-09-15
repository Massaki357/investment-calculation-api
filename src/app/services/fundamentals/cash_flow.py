"""Cash-flow metrics."""

from app.services.fundamentals.profitability import nopat
from app.utils.math import safe_divide


def free_cash_flow(operating_cash_flow: float, capital_expenditures: float) -> float:
    """FCF = operating_cash_flow − capital_expenditures."""
    return operating_cash_flow - capital_expenditures


def free_cash_flow_to_firm(
    ebit: float,
    tax_rate: float,
    depreciation_amortization: float,
    capital_expenditures: float,
    change_in_working_capital: float,
) -> float:
    """FCFF = ebit × (1 − tax_rate) + D&A − capex − ΔNWC."""
    return (
        nopat(ebit, tax_rate)
        + depreciation_amortization
        - capital_expenditures
        - change_in_working_capital
    )


def free_cash_flow_to_equity(
    free_cash_flow_to_firm: float,
    interest_expense: float,
    tax_rate: float,
    net_borrowing: float,
) -> float:
    """FCFE = FCFF − interest_expense × (1 − tax_rate) + net_borrowing."""
    return free_cash_flow_to_firm - interest_expense * (1 - tax_rate) + net_borrowing


def fcf_conversion(free_cash_flow: float, net_income: float) -> float:
    """FCF Conversion = free_cash_flow / net_income."""
    return safe_divide(free_cash_flow, net_income, denominator_name="net_income")


def cash_conversion_ratio(operating_cash_flow: float, net_income: float) -> float:
    """Cash Conversion Ratio = operating_cash_flow / net_income."""
    return safe_divide(operating_cash_flow, net_income, denominator_name="net_income")


def cfo_margin(operating_cash_flow: float, revenue: float) -> float:
    """CFO Margin = operating_cash_flow / revenue."""
    return safe_divide(operating_cash_flow, revenue, denominator_name="revenue")


def capex_to_revenue(capital_expenditures: float, revenue: float) -> float:
    """Capex/Revenue = capital_expenditures / revenue."""
    return safe_divide(capital_expenditures, revenue, denominator_name="revenue")


def capex_to_depreciation(capital_expenditures: float, depreciation_amortization: float) -> float:
    """Capex/Depreciation = capital_expenditures / depreciation_amortization."""
    return safe_divide(
        capital_expenditures,
        depreciation_amortization,
        denominator_name="depreciation_amortization",
    )


def cash_flow_per_share(operating_cash_flow: float, shares_outstanding: float) -> float:
    """Cash Flow per Share = operating_cash_flow / shares_outstanding."""
    return safe_divide(
        operating_cash_flow, shares_outstanding, denominator_name="shares_outstanding"
    )


def owner_earnings(
    net_income: float,
    depreciation_amortization: float,
    maintenance_capital_expenditures: float,
    change_in_working_capital: float,
) -> float:
    """Owner Earnings (Buffett) = net_income + D&A − maintenance capex − ΔNWC."""
    return (
        net_income
        + depreciation_amortization
        - maintenance_capital_expenditures
        - change_in_working_capital
    )
