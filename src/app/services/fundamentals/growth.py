"""Growth rates, CAGR and reinvestment metrics."""

from app.core.exceptions import DivisionByZeroError, InvalidInputError, NonFiniteResultError
from app.services.fundamentals.profitability import nopat
from app.utils.math import safe_divide
from app.utils.validation import ensure_finite


def growth_rate(current_value: float, previous_value: float) -> float:
    """Growth = (current_value − previous_value) / |previous_value|.

    Using the absolute value keeps the sign meaningful when the base is negative:
    going from −100 to −50 is +50%.
    """
    if previous_value == 0:
        raise DivisionByZeroError("previous_value cannot be zero")
    return (current_value - previous_value) / abs(previous_value)


def cagr(
    beginning_value: float,
    ending_value: float,
    years: float,
    *,
    beginning_name: str = "beginning_value",
    ending_name: str = "ending_value",
) -> float:
    """CAGR = (ending_value / beginning_value) ^ (1 / years) − 1.

    Requires strictly positive beginning and ending values: with a sign change or zero the
    real-valued root is undefined.
    """
    if beginning_value <= 0:
        raise InvalidInputError(f"{beginning_name} must be greater than zero for CAGR")
    if ending_value <= 0:
        raise InvalidInputError(f"{ending_name} must be greater than zero for CAGR")
    if years <= 0:
        raise InvalidInputError("years must be greater than zero")
    try:
        result = (ending_value / beginning_value) ** (1 / years) - 1
    except OverflowError as exc:
        raise NonFiniteResultError("CAGR is too large to be represented") from exc
    return ensure_finite(result, "CAGR")


def sustainable_growth_rate(return_on_equity: float, retention_ratio: float) -> float:
    """SGR = return_on_equity × retention_ratio."""
    return return_on_equity * retention_ratio


def retention_ratio(net_income: float, dividends_paid: float) -> float:
    """Retention Ratio = (net_income − dividends_paid) / net_income = 1 − payout ratio."""
    return safe_divide(net_income - dividends_paid, net_income, denominator_name="net_income")


def reinvestment_rate(
    capital_expenditures: float,
    depreciation_amortization: float,
    change_in_working_capital: float,
    ebit: float,
    tax_rate: float,
) -> float:
    """Reinvestment Rate = (capex − D&A + ΔNWC) / NOPAT (Damodaran)."""
    return safe_divide(
        capital_expenditures - depreciation_amortization + change_in_working_capital,
        nopat(ebit, tax_rate),
        denominator_name="nopat (ebit × (1 - tax_rate))",
    )
