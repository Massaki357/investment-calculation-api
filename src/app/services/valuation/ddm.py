"""Dividend discount models."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.core.exceptions import InvalidInputError
from app.services.valuation.time_value import discount_cash_flows, discount_factor
from app.utils.validation import ensure_finite


def dividend_discount_model(
    dividends: Sequence[float], cost_of_equity: float, terminal_price: float = 0
) -> float:
    """Value = Σ D_t / (1 + r)^t + terminal_price / (1 + r)^n."""
    if not dividends:
        raise InvalidInputError("dividends must contain at least one value")
    pv_dividends = sum(
        item.present_value
        for item in discount_cash_flows(dividends, cost_of_equity, rate_name="cost_of_equity")
    )
    pv_terminal = terminal_price * discount_factor(
        cost_of_equity, len(dividends), rate_name="cost_of_equity"
    )
    return ensure_finite(pv_dividends + pv_terminal, "value")


def gordon_growth_value(next_dividend: float, cost_of_equity: float, growth_rate: float) -> float:
    """Gordon Growth: P0 = D1 / (r − g), requires r > g."""
    if cost_of_equity <= growth_rate:
        raise InvalidInputError("cost_of_equity must be greater than growth_rate")
    return ensure_finite(next_dividend / (cost_of_equity - growth_rate), "value")


class DividendStage(StrEnum):
    HIGH_GROWTH = "high_growth"
    TRANSITION = "transition"


@dataclass(frozen=True, slots=True)
class DividendProjection:
    period: int
    stage: DividendStage
    growth_rate: float
    dividend: float
    discount_factor: float
    present_value: float


@dataclass(frozen=True, slots=True)
class MultiStageDdmResult:
    projections: list[DividendProjection]
    present_value_of_dividends: float
    terminal_dividend: float
    terminal_value: float
    present_value_of_terminal_value: float
    value: float

    @property
    def terminal_value_percentage(self) -> float | None:
        if self.value == 0:
            return None
        return self.present_value_of_terminal_value / self.value


def _multi_stage_ddm(
    current_dividend: float,
    growth_path: Sequence[tuple[DividendStage, float]],
    stable_growth_rate: float,
    cost_of_equity: float,
    stable_cost_of_equity: float | None,
) -> MultiStageDdmResult:
    stable_rate = cost_of_equity if stable_cost_of_equity is None else stable_cost_of_equity
    if stable_rate <= stable_growth_rate:
        raise InvalidInputError(
            "stable-stage cost of equity must be greater than stable_growth_rate"
        )

    projections: list[DividendProjection] = []
    dividend = current_dividend
    for period, (stage, growth) in enumerate(growth_path, start=1):
        dividend = ensure_finite(dividend * (1 + growth), "projected dividend")
        factor = discount_factor(cost_of_equity, period, rate_name="cost_of_equity")
        projections.append(
            DividendProjection(
                period=period,
                stage=stage,
                growth_rate=growth,
                dividend=dividend,
                discount_factor=factor,
                present_value=dividend * factor,
            )
        )

    horizon = len(growth_path)
    terminal_dividend = ensure_finite(dividend * (1 + stable_growth_rate), "terminal dividend")
    terminal_value = ensure_finite(
        terminal_dividend / (stable_rate - stable_growth_rate), "terminal value"
    )
    pv_terminal = terminal_value * discount_factor(
        cost_of_equity, horizon, rate_name="cost_of_equity"
    )
    pv_dividends = sum(item.present_value for item in projections)

    return MultiStageDdmResult(
        projections=projections,
        present_value_of_dividends=ensure_finite(pv_dividends, "present value of dividends"),
        terminal_dividend=terminal_dividend,
        terminal_value=terminal_value,
        present_value_of_terminal_value=ensure_finite(pv_terminal, "present value of terminal"),
        value=ensure_finite(pv_dividends + pv_terminal, "value"),
    )


def two_stage_ddm(
    current_dividend: float,
    high_growth_rate: float,
    high_growth_years: int,
    stable_growth_rate: float,
    cost_of_equity: float,
    stable_cost_of_equity: float | None = None,
) -> MultiStageDdmResult:
    """Two-stage DDM.

    D_t = D0 × (1 + g1)^t for t = 1..n
    P_n = D_n × (1 + g2) / (r_stable − g2)
    Value = Σ D_t / (1 + r)^t + P_n / (1 + r)^n
    """
    if high_growth_years < 1:
        raise InvalidInputError("high_growth_years must be at least 1")
    path = [(DividendStage.HIGH_GROWTH, high_growth_rate)] * high_growth_years
    return _multi_stage_ddm(
        current_dividend, path, stable_growth_rate, cost_of_equity, stable_cost_of_equity
    )


def three_stage_ddm(
    current_dividend: float,
    high_growth_rate: float,
    high_growth_years: int,
    transition_years: int,
    stable_growth_rate: float,
    cost_of_equity: float,
    stable_cost_of_equity: float | None = None,
) -> MultiStageDdmResult:
    """Three-stage DDM with linear growth decline during the transition (Damodaran).

    Transition growth in year j (1..T): g_j = g1 − (g1 − g2) × j / T, reaching g2 at year T.
    Terminal price at n + T: P = D_{n+T} × (1 + g2) / (r_stable − g2).
    """
    if high_growth_years < 1:
        raise InvalidInputError("high_growth_years must be at least 1")
    if transition_years < 1:
        raise InvalidInputError("transition_years must be at least 1")
    step = (high_growth_rate - stable_growth_rate) / transition_years
    path = [(DividendStage.HIGH_GROWTH, high_growth_rate)] * high_growth_years + [
        (DividendStage.TRANSITION, high_growth_rate - step * year)
        for year in range(1, transition_years + 1)
    ]
    return _multi_stage_ddm(
        current_dividend, path, stable_growth_rate, cost_of_equity, stable_cost_of_equity
    )
