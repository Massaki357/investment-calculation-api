"""Time value of money: compounding and discounting."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError, NonFiniteResultError
from app.utils.validation import ensure_finite


def _growth_factor(rate: float, periods: float, *, rate_name: str) -> float:
    if rate <= -1:
        raise InvalidInputError(f"{rate_name} must be greater than -1")
    try:
        factor = (1 + rate) ** periods
    except OverflowError as exc:
        raise NonFiniteResultError("compounding factor is too large to be represented") from exc
    return ensure_finite(factor, "compounding factor")


def discount_factor(rate: float, period: float, *, rate_name: str = "discount_rate") -> float:
    """Discount factor = 1 / (1 + rate) ^ period."""
    factor = _growth_factor(rate, period, rate_name=rate_name)
    if factor == 0:
        raise NonFiniteResultError("discount factor is too large to be represented")
    return ensure_finite(1 / factor, "discount factor")


def present_value(amount: float, rate: float, periods: float) -> float:
    """PV = amount / (1 + rate) ^ periods."""
    return ensure_finite(amount * discount_factor(rate, periods, rate_name="rate"), "present value")


def future_value(present_value: float, rate: float, periods: float) -> float:
    """FV = present_value × (1 + rate) ^ periods."""
    return ensure_finite(
        present_value * _growth_factor(rate, periods, rate_name="rate"), "future value"
    )


@dataclass(frozen=True, slots=True)
class DiscountedCashFlow:
    period: float
    cash_flow: float
    discount_factor: float
    present_value: float


def cash_flow_periods(count: int, *, mid_year_convention: bool = False) -> list[float]:
    """Timing of cash flows 1..count: end of period (i) or mid-period (i − 0.5)."""
    offset = 0.5 if mid_year_convention else 0.0
    return [index - offset for index in range(1, count + 1)]


def discount_cash_flows(
    cash_flows: Sequence[float],
    rate: float,
    periods: Sequence[float] | None = None,
    *,
    mid_year_convention: bool = False,
    rate_name: str = "discount_rate",
) -> list[DiscountedCashFlow]:
    """Discount each cash flow: PV_i = CF_i / (1 + rate) ^ t_i."""
    if periods is None:
        periods = cash_flow_periods(len(cash_flows), mid_year_convention=mid_year_convention)
    elif len(periods) != len(cash_flows):
        raise InvalidInputError("periods must have the same length as cash_flows")

    discounted = []
    for cash_flow, period in zip(cash_flows, periods, strict=True):
        if period < 0:
            raise InvalidInputError("periods cannot be negative")
        factor = discount_factor(rate, period, rate_name=rate_name)
        discounted.append(
            DiscountedCashFlow(
                period=period,
                cash_flow=cash_flow,
                discount_factor=factor,
                present_value=ensure_finite(cash_flow * factor, "present value"),
            )
        )
    return discounted
