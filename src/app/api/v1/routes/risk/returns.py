from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.api.v1.routes.risk.common import (
    ANNUAL_RATE_NOTE,
    PRICES_EXAMPLE,
    RETURNS_EXAMPLE,
    SERIES_NOTE,
    single_returns,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.risk import (
    AnnualizedSeriesRequest,
    DispersionRequest,
    DownsideDeviationRequest,
    PricesToReturnsRequest,
    ReturnsResponse,
    SeriesRequest,
)
from app.services.risk import performance, returns
from app.services.statistics import descriptive

router = APIRouter(tags=["Risk · Returns and dispersion"])


def _returns(r: PricesToReturnsRequest) -> ReturnsResponse:
    series = returns.returns_from_prices(r.prices, r.return_type)
    return ReturnsResponse(return_type=r.return_type, observations=len(series), returns=series)


def _volatility(r: DispersionRequest) -> MetricBreakdownResponse:
    periodic = descriptive.standard_deviation(single_returns(r), population=r.population)
    return MetricBreakdownResponse(
        metric="Annualized Volatility",
        value=returns.annualize_dispersion(periodic, r.periods_per_year),
        unit=Unit.DECIMAL,
        components=[MetricValue(metric="Periodic Volatility", value=periodic, unit=Unit.DECIMAL)],
    )


def _variance(r: DispersionRequest) -> MetricBreakdownResponse:
    periodic = descriptive.variance(single_returns(r), population=r.population)
    return MetricBreakdownResponse(
        metric="Variance",
        value=periodic,
        unit=Unit.NUMBER,
        components=[
            MetricValue(
                metric="Annualized Variance", value=periodic * r.periods_per_year, unit=Unit.NUMBER
            )
        ],
    )


def _downside_deviation(r: DownsideDeviationRequest) -> MetricBreakdownResponse:
    periodic = performance.downside_deviation(
        single_returns(r), r.minimum_acceptable_return, r.periods_per_year, r.return_type
    )
    return MetricBreakdownResponse(
        metric="Annualized Downside Deviation",
        value=returns.annualize_dispersion(periodic, r.periods_per_year),
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Periodic Downside Deviation", value=periodic, unit=Unit.DECIMAL)
        ],
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/cumulative-return",
        metric="Cumulative Return",
        unit=Unit.DECIMAL,
        summary="Cumulative return (retorno acumulado)",
        formula="simple: Π(1 + r_t) − 1 · log: e^(Σ r_t) − 1",
        request_model=SeriesRequest,
        compute=lambda r: returns.cumulative_return(single_returns(r), r.return_type),
        example={"prices": PRICES_EXAMPLE},
        notes=(SERIES_NOTE, "From prices this equals last / first − 1."),
    ),
    MetricEndpoint(
        path="/annualized-return",
        metric="Annualized Return",
        unit=Unit.DECIMAL,
        summary="Geometric annualized return (retorno anualizado)",
        formula="(1 + cumulative_return)^(periods_per_year / n) − 1",
        request_model=AnnualizedSeriesRequest,
        compute=lambda r: returns.annualized_return(
            single_returns(r), r.return_type, r.periods_per_year
        ),
        example={"returns": RETURNS_EXAMPLE, "periods_per_year": 252},
        notes=(SERIES_NOTE, "n is the number of return periods."),
    ),
    MetricEndpoint(
        path="/standard-deviation",
        metric="Standard Deviation",
        unit=Unit.DECIMAL,
        summary="Periodic standard deviation of returns (desvio padrão)",
        formula="σ = √(Σ (r − r̄)² / (n − ddof)), ddof = 1 unless population",
        request_model=DispersionRequest,
        compute=lambda r: descriptive.standard_deviation(
            single_returns(r), population=r.population
        ),
        example={"returns": RETURNS_EXAMPLE},
        notes=(SERIES_NOTE, "Not annualized; see /volatility for σ × √periods_per_year."),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/returns",
        title="Returns",
        summary="Periodic returns from prices (retorno)",
        formulas=("simple: r_t = P_t / P_{t−1} − 1", "log: r_t = ln(P_t / P_{t−1})"),
        request_model=PricesToReturnsRequest,
        response_model=ReturnsResponse,
        compute=_returns,
        examples={
            "simple": {"prices": [100.0, 102.0, 99.96]},
            "log": {"prices": [100.0, 102.0, 99.96], "return_type": "log"},
        },
        notes=("Returns n − 1 returns for n prices.",),
    ),
    CalculationEndpoint(
        path="/volatility",
        title="Volatility",
        summary="Annualized volatility of returns (volatilidade)",
        formulas=("σ_annual = σ_periodic × √periods_per_year",),
        request_model=DispersionRequest,
        response_model=MetricBreakdownResponse,
        compute=_volatility,
        examples={"daily_returns": {"returns": RETURNS_EXAMPLE, "periods_per_year": 252}},
        notes=(SERIES_NOTE, "Sample standard deviation unless population is true."),
    ),
    CalculationEndpoint(
        path="/variance",
        title="Variance",
        summary="Variance of returns (variância)",
        formulas=(
            "σ² = Σ (r − r̄)² / (n − ddof)",
            "annualized variance = σ² × periods_per_year",
        ),
        request_model=DispersionRequest,
        response_model=MetricBreakdownResponse,
        compute=_variance,
        examples={"daily_returns": {"returns": RETURNS_EXAMPLE}},
        notes=(SERIES_NOTE, "value is the periodic variance; the annualized one is a component."),
    ),
    CalculationEndpoint(
        path="/downside-deviation",
        title="Downside Deviation",
        summary="Downside deviation below a minimum acceptable return",
        formulas=(
            "DD_periodic = √(Σ min(r_t − MAR_p, 0)² / N)",
            "DD_annual = DD_periodic × √periods_per_year",
        ),
        request_model=DownsideDeviationRequest,
        response_model=MetricBreakdownResponse,
        compute=_downside_deviation,
        examples={"zero_mar": {"returns": RETURNS_EXAMPLE, "minimum_acceptable_return": 0}},
        notes=(
            SERIES_NOTE,
            "N counts all observations, not only those below MAR (Sortino & Price).",
            "minimum_acceptable_return is annual. " + ANNUAL_RATE_NOTE,
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
