from dataclasses import asdict
from typing import cast

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.schemas.common import Unit
from app.schemas.valuation import ddm as schemas
from app.schemas.valuation.ddm import (
    DividendProjectionItem,
    MultiStageDdmResponse,
    ThreeStageDdmRequest,
    TwoStageDdmRequest,
)
from app.services.valuation import ddm as calc
from app.services.valuation.ddm import MultiStageDdmResult

router = APIRouter(tags=["Valuation · Dividend discount models"])

STABLE_RATE_NOTE = (
    "stable_cost_of_equity (optional) is used only in the terminal price; explicit dividends and "
    "the terminal price are discounted at cost_of_equity."
)


def _gordon(r: schemas.GordonGrowthRequest) -> float:
    # The request validator guarantees exactly one of next_dividend / current_dividend.
    if r.next_dividend is not None:
        next_dividend = r.next_dividend
    else:
        next_dividend = cast(float, r.current_dividend) * (1 + r.growth_rate)
    return calc.gordon_growth_value(next_dividend, r.cost_of_equity, r.growth_rate)


def _response(
    metric: str, result: MultiStageDdmResult, currency: str | None
) -> MultiStageDdmResponse:
    return MultiStageDdmResponse(
        metric=metric,
        value=result.value,
        present_value_of_dividends=result.present_value_of_dividends,
        terminal_dividend=result.terminal_dividend,
        terminal_value=result.terminal_value,
        present_value_of_terminal_value=result.present_value_of_terminal_value,
        terminal_value_percentage=result.terminal_value_percentage,
        projections=[DividendProjectionItem(**asdict(item)) for item in result.projections],
        currency=currency,
    )


def _two_stage(r: TwoStageDdmRequest) -> MultiStageDdmResponse:
    result = calc.two_stage_ddm(
        r.current_dividend,
        r.high_growth_rate,
        r.high_growth_years,
        r.stable_growth_rate,
        r.cost_of_equity,
        r.stable_cost_of_equity,
    )
    return _response("Two-Stage DDM", result, r.currency)


def _three_stage(r: ThreeStageDdmRequest) -> MultiStageDdmResponse:
    result = calc.three_stage_ddm(
        r.current_dividend,
        r.high_growth_rate,
        r.high_growth_years,
        r.transition_years,
        r.stable_growth_rate,
        r.cost_of_equity,
        r.stable_cost_of_equity,
    )
    return _response("Three-Stage DDM", result, r.currency)


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/ddm",
        metric="Dividend Discount Model",
        unit=Unit.AMOUNT,
        summary="Dividend discount model with explicit dividends",
        formula="Value = Σ D_t / (1 + cost_of_equity)^t + terminal_price / (1 + cost_of_equity)^n",
        request_model=schemas.DdmRequest,
        compute=lambda r: calc.dividend_discount_model(
            r.dividends, r.cost_of_equity, r.terminal_price
        ),
        example={"dividends": [2.0, 2.1, 2.2], "cost_of_equity": 0.10, "terminal_price": 40.0},
        notes=("Dividends at the end of each period; terminal_price defaults to 0.",),
    ),
    MetricEndpoint(
        path="/gordon-growth",
        metric="Gordon Growth Model",
        unit=Unit.AMOUNT,
        summary="Gordon growth model (constant growth DDM)",
        formula="P0 = D1 / (cost_of_equity − growth_rate), with D1 = D0 × (1 + growth_rate)",
        request_model=schemas.GordonGrowthRequest,
        compute=_gordon,
        example={"current_dividend": 2.0, "cost_of_equity": 0.10, "growth_rate": 0.05},
        notes=(
            "Send next_dividend (D1) or current_dividend (D0), not both.",
            "cost_of_equity ≤ growth_rate returns INVALID_INPUT.",
        ),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/ddm/two-stage",
        title="Two-Stage DDM",
        summary="Two-stage dividend discount model",
        formulas=(
            "D_t = D0 × (1 + high_growth_rate)^t, t = 1..n",
            "P_n = D_n × (1 + stable_growth_rate) / (stable_cost_of_equity − stable_growth_rate)",
            "Value = Σ D_t / (1 + cost_of_equity)^t + P_n / (1 + cost_of_equity)^n",
        ),
        request_model=TwoStageDdmRequest,
        response_model=MultiStageDdmResponse,
        compute=_two_stage,
        examples={
            "two_stage": {
                "current_dividend": 1.0,
                "high_growth_rate": 0.10,
                "high_growth_years": 2,
                "stable_growth_rate": 0.03,
                "cost_of_equity": 0.10,
            }
        },
        notes=(STABLE_RATE_NOTE, "The stable-stage cost of equity must exceed stable growth."),
    ),
    CalculationEndpoint(
        path="/ddm/three-stage",
        title="Three-Stage DDM",
        summary="Three-stage dividend discount model with a linear growth transition",
        formulas=(
            "High growth: D_t = D_{t−1} × (1 + g1), t = 1..n",
            "Transition year j = 1..T: g_j = g1 − (g1 − g2) × j / T",
            "P_{n+T} = D_{n+T} × (1 + g2) / (stable_cost_of_equity − g2)",
            "Value = Σ D_t / (1 + cost_of_equity)^t + P_{n+T} / (1 + cost_of_equity)^(n+T)",
        ),
        request_model=ThreeStageDdmRequest,
        response_model=MultiStageDdmResponse,
        compute=_three_stage,
        examples={
            "three_stage": {
                "current_dividend": 1.0,
                "high_growth_rate": 0.10,
                "high_growth_years": 1,
                "transition_years": 2,
                "stable_growth_rate": 0.04,
                "cost_of_equity": 0.10,
            }
        },
        notes=(
            "Growth declines linearly and reaches stable_growth_rate in the last transition year "
            "(Damodaran).",
            STABLE_RATE_NOTE,
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
