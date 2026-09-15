"""Discounted cash flow valuation building blocks."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import InvalidInputError
from app.services.valuation.time_value import (
    DiscountedCashFlow,
    discount_cash_flows,
    discount_factor,
)
from app.utils.math import safe_divide
from app.utils.validation import ensure_finite


def perpetuity_growth_terminal_value(
    final_cash_flow: float, discount_rate: float, growth_rate: float
) -> float:
    """Terminal Value (Gordon) = final_cash_flow × (1 + g) / (r − g), requires r > g."""
    if discount_rate <= growth_rate:
        raise InvalidInputError("discount_rate must be greater than growth_rate")
    return ensure_finite(
        final_cash_flow * (1 + growth_rate) / (discount_rate - growth_rate), "terminal value"
    )


def exit_multiple_terminal_value(terminal_metric: float, multiple: float) -> float:
    """Terminal Value (exit multiple) = terminal_metric × multiple (e.g. EBITDA_n × EV/EBITDA)."""
    return ensure_finite(terminal_metric * multiple, "terminal value")


def enterprise_value(
    present_value_of_cash_flows: float, present_value_of_terminal_value: float
) -> float:
    """Enterprise Value = Σ PV(FCFF) + PV(terminal value)."""
    return ensure_finite(
        present_value_of_cash_flows + present_value_of_terminal_value, "enterprise value"
    )


def equity_value(
    enterprise_value: float,
    net_debt: float,
    minority_interest: float = 0,
    non_operating_assets: float = 0,
) -> float:
    """Equity Value = EV − net_debt − minority_interest + non_operating_assets."""
    return ensure_finite(
        enterprise_value - net_debt - minority_interest + non_operating_assets, "equity value"
    )


def value_per_share(equity_value: float, shares_outstanding: float) -> float:
    """Intrinsic value per share = equity_value / shares_outstanding."""
    return safe_divide(equity_value, shares_outstanding, denominator_name="shares_outstanding")


def margin_of_safety(intrinsic_value: float, market_price: float) -> float:
    """Margin of Safety = (intrinsic_value − market_price) / intrinsic_value.

    Requires intrinsic_value > 0: with a negative denominator the sign flips and the ratio
    would read as a large positive margin.
    """
    if intrinsic_value <= 0:
        raise InvalidInputError("intrinsic_value must be greater than zero for margin of safety")
    return safe_divide(
        intrinsic_value - market_price, intrinsic_value, denominator_name="intrinsic_value"
    )


@dataclass(frozen=True, slots=True)
class DiscountedValuation:
    discounted_cash_flows: list[DiscountedCashFlow]
    present_value_of_cash_flows: float
    terminal_value: float
    terminal_discount_factor: float
    present_value_of_terminal_value: float
    total_value: float

    @property
    def terminal_value_percentage(self) -> float | None:
        """Share of the total value coming from the terminal value (None when total is 0)."""
        if self.total_value == 0:
            return None
        return self.present_value_of_terminal_value / self.total_value


def discounted_valuation(
    cash_flows: Sequence[float],
    discount_rate: float,
    terminal_value: float,
    *,
    mid_year_convention: bool = False,
) -> DiscountedValuation:
    """Total = Σ CF_t / (1 + r)^t + TV / (1 + r)^n, with TV discounted from the end of period n."""
    if not cash_flows:
        raise InvalidInputError("cash_flows must contain at least one value")

    discounted = discount_cash_flows(
        cash_flows, discount_rate, mid_year_convention=mid_year_convention
    )
    pv_cash_flows = ensure_finite(
        sum(item.present_value for item in discounted), "present value of cash flows"
    )
    terminal_factor = discount_factor(discount_rate, len(cash_flows))
    pv_terminal = ensure_finite(terminal_value * terminal_factor, "present value of terminal value")

    return DiscountedValuation(
        discounted_cash_flows=discounted,
        present_value_of_cash_flows=pv_cash_flows,
        terminal_value=terminal_value,
        terminal_discount_factor=terminal_factor,
        present_value_of_terminal_value=pv_terminal,
        total_value=ensure_finite(pv_cash_flows + pv_terminal, "total value"),
    )
