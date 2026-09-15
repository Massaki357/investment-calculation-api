from collections.abc import Callable

from fastapi import APIRouter

from app.api.endpoint_specs import CalculationEndpoint, add_calculation_endpoints
from app.api.v1.routes.risk.common import (
    PRICES_EXAMPLE,
    RETURNS_EXAMPLE,
    SERIES_NOTE,
    single_returns,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.risk import (
    DrawdownResponse,
    ExpectedShortfallRequest,
    ParametricVarRequest,
    SeriesRequest,
    TailMethod,
    TailRiskRequest,
)
from app.services.risk import drawdown, tail
from app.services.risk.returns import wealth_index
from app.services.risk.tail import TailRisk

router = APIRouter(tags=["Risk · Drawdown and tail risk"])

LOSS_NOTE = (
    "Reported as a positive loss in return units (0.03 = 3% loss); a negative value means the "
    "quantile is a gain."
)
HORIZON_NOTE = (
    "horizon_periods scales one-period results by √h (square-root-of-time approximation)."
)
TAIL_EXAMPLE = {"returns": RETURNS_EXAMPLE, "confidence": 0.95}


def _drawdown(r: SeriesRequest) -> DrawdownResponse:
    path = r.prices if r.prices is not None else wealth_index(single_returns(r), r.return_type)
    result = drawdown.maximum_drawdown(path)
    return DrawdownResponse(
        max_drawdown=result.max_drawdown,
        peak_index=result.peak_index,
        trough_index=result.trough_index,
        recovery_index=result.recovery_index,
        duration_periods=result.duration_periods,
    )


def _context(result: TailRisk) -> list[MetricValue]:
    return [
        MetricValue(metric="Confidence", value=result.confidence, unit=Unit.DECIMAL),
        MetricValue(metric="Horizon Periods", value=result.horizon_periods, unit=Unit.NUMBER),
    ]


def _var_response(metric: str, result: TailRisk) -> MetricBreakdownResponse:
    return MetricBreakdownResponse(
        metric=metric, value=result.value_at_risk, unit=Unit.DECIMAL, components=_context(result)
    )


def _historical_var(r: TailRiskRequest) -> MetricBreakdownResponse:
    result = tail.historical_tail_risk(single_returns(r), r.confidence, r.horizon_periods)
    return _var_response("Historical VaR", result)


def _parametric_var(r: ParametricVarRequest) -> MetricBreakdownResponse:
    result = tail.parametric_tail_risk(
        single_returns(r), r.confidence, r.horizon_periods, include_mean=r.include_mean
    )
    return _var_response("Parametric VaR", result)


def _shortfall(metric: str) -> Callable[[ExpectedShortfallRequest], MetricBreakdownResponse]:
    def compute(r: ExpectedShortfallRequest) -> MetricBreakdownResponse:
        series = single_returns(r)
        if r.method is TailMethod.PARAMETRIC:
            result = tail.parametric_tail_risk(
                series, r.confidence, r.horizon_periods, include_mean=r.include_mean
            )
        else:
            result = tail.historical_tail_risk(series, r.confidence, r.horizon_periods)
        return MetricBreakdownResponse(
            metric=metric,
            value=result.expected_shortfall,
            unit=Unit.DECIMAL,
            components=[
                MetricValue(
                    metric=f"VaR ({r.method.value})", value=result.value_at_risk, unit=Unit.DECIMAL
                ),
                *_context(result),
            ],
        )

    return compute


SHORTFALL_FORMULAS = (
    "historical: ES = −mean(r_t | r_t ≤ q_(1−c)), q = empirical quantile (linear)",
    "parametric: ES = −(μ − σ × φ(z) / (1 − c)), z = Φ⁻¹(c)",
)
SHORTFALL_NOTES = (
    SERIES_NOTE,
    LOSS_NOTE,
    HORIZON_NOTE,
    "Conditional VaR and Expected Shortfall are the same measure and share one implementation.",
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/maximum-drawdown",
        title="Maximum Drawdown",
        summary="Maximum peak-to-trough decline",
        formulas=("MDD = min_t (W_t / max_{s≤t} W_s − 1)",),
        request_model=SeriesRequest,
        response_model=DrawdownResponse,
        compute=_drawdown,
        examples={"prices": {"prices": PRICES_EXAMPLE}, "returns": {"returns": RETURNS_EXAMPLE}},
        notes=(
            SERIES_NOTE,
            "With prices, W = prices and indices refer to the price list. With returns, W is the "
            "wealth index starting at 1 (index 0 = before the first return).",
            "Negative decimal; indices are null when there is no drawdown.",
        ),
    ),
    CalculationEndpoint(
        path="/var/historical",
        title="Historical VaR",
        summary="Historical value at risk",
        formulas=(
            "VaR = −q_(1−confidence) × √h, q = empirical quantile with linear interpolation",
        ),
        request_model=TailRiskRequest,
        response_model=MetricBreakdownResponse,
        compute=_historical_var,
        examples={"one_day_95": TAIL_EXAMPLE},
        notes=(SERIES_NOTE, LOSS_NOTE, HORIZON_NOTE),
    ),
    CalculationEndpoint(
        path="/var/parametric",
        title="Parametric VaR",
        summary="Parametric (normal) value at risk",
        formulas=("VaR = −(μ × h − z × σ × √h), z = Φ⁻¹(confidence)",),
        request_model=ParametricVarRequest,
        response_model=MetricBreakdownResponse,
        compute=_parametric_var,
        examples={
            "one_day_95": TAIL_EXAMPLE,
            "ten_day_99": {**TAIL_EXAMPLE, "confidence": 0.99, "horizon_periods": 10},
        },
        notes=(
            SERIES_NOTE,
            LOSS_NOTE,
            "Assumes normally distributed returns; μ and sample σ are estimated from the series.",
            "include_mean = false sets μ = 0.",
        ),
    ),
    CalculationEndpoint(
        path="/cvar",
        title="Conditional VaR",
        summary="Conditional value at risk (CVaR)",
        formulas=SHORTFALL_FORMULAS,
        request_model=ExpectedShortfallRequest,
        response_model=MetricBreakdownResponse,
        compute=_shortfall("Conditional VaR"),
        examples={
            "historical": TAIL_EXAMPLE,
            "parametric": {**TAIL_EXAMPLE, "method": "parametric"},
        },
        notes=SHORTFALL_NOTES,
    ),
    CalculationEndpoint(
        path="/expected-shortfall",
        title="Expected Shortfall",
        summary="Expected shortfall (ES)",
        formulas=SHORTFALL_FORMULAS,
        request_model=ExpectedShortfallRequest,
        response_model=MetricBreakdownResponse,
        compute=_shortfall("Expected Shortfall"),
        examples={
            "historical": TAIL_EXAMPLE,
            "parametric": {**TAIL_EXAMPLE, "method": "parametric"},
        },
        notes=SHORTFALL_NOTES,
    ),
)

METRIC_ENDPOINTS = ()

add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
