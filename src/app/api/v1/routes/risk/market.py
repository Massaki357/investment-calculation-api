from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.api.v1.routes.risk.common import (
    ANNUAL_RATE_NOTE,
    BENCHMARK_EXAMPLE,
    PAIRED_NOTE,
    RETURNS_EXAMPLE,
    paired_returns,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.risk import PairedCovarianceRequest, PairedRiskFreeRequest, PairedSeriesRequest
from app.services.risk import performance
from app.services.statistics import relationships

router = APIRouter(tags=["Risk · Market sensitivity"])

PAIRED_EXAMPLE = {"asset_returns": RETURNS_EXAMPLE, "benchmark_returns": BENCHMARK_EXAMPLE}
NAMES = {"x_name": "asset_returns", "y_name": "benchmark_returns"}


def _alpha(r: PairedRiskFreeRequest) -> MetricBreakdownResponse:
    asset, benchmark = paired_returns(r)
    result = performance.regression_alpha(
        asset, benchmark, r.risk_free_rate, r.periods_per_year, r.return_type
    )
    return MetricBreakdownResponse(
        metric="Alpha",
        value=result.annualized_alpha,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Periodic Alpha", value=result.periodic_alpha, unit=Unit.DECIMAL),
            MetricValue(metric="Beta", value=result.beta, unit=Unit.NUMBER),
        ],
    )


def _beta(r: PairedSeriesRequest) -> float:
    asset, benchmark = paired_returns(r)
    return performance.beta(asset, benchmark)


def _correlation(r: PairedSeriesRequest) -> float:
    asset, benchmark = paired_returns(r)
    return relationships.correlation(asset, benchmark, **NAMES)


def _covariance(r: PairedCovarianceRequest) -> float:
    asset, benchmark = paired_returns(r)
    return relationships.covariance(asset, benchmark, population=r.population, **NAMES)


def _r_squared(r: PairedSeriesRequest) -> float:
    asset, benchmark = paired_returns(r)
    return relationships.r_squared(asset, benchmark, **NAMES)


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/beta",
        metric="Beta",
        unit=Unit.NUMBER,
        summary="Beta of an asset against a benchmark",
        formula="β = cov(asset, benchmark) / var(benchmark)",
        request_model=PairedSeriesRequest,
        compute=_beta,
        example=PAIRED_EXAMPLE,
        notes=(PAIRED_NOTE, "A constant benchmark returns DIVISION_BY_ZERO."),
    ),
    MetricEndpoint(
        path="/correlation",
        metric="Correlation",
        unit=Unit.NUMBER,
        summary="Pearson correlation between asset and benchmark returns (correlação)",
        formula="ρ = Σ (a − ā)(b − b̄) / √(Σ (a − ā)² × Σ (b − b̄)²)",
        request_model=PairedSeriesRequest,
        compute=_correlation,
        example=PAIRED_EXAMPLE,
        notes=(PAIRED_NOTE, "Result in [−1, 1]; a constant series returns DIVISION_BY_ZERO."),
    ),
    MetricEndpoint(
        path="/covariance",
        metric="Covariance",
        unit=Unit.NUMBER,
        summary="Covariance of asset and benchmark returns (covariância)",
        formula="cov = Σ (a − ā)(b − b̄) / (n − ddof), ddof = 1 unless population",
        request_model=PairedCovarianceRequest,
        compute=_covariance,
        example=PAIRED_EXAMPLE,
        notes=(
            PAIRED_NOTE,
            "Periodic (not annualized); multiply by periods_per_year to annualize.",
        ),
    ),
    MetricEndpoint(
        path="/r-squared",
        metric="R²",
        unit=Unit.NUMBER,
        summary="Coefficient of determination of asset returns on benchmark returns",
        formula="R² = ρ(asset, benchmark)²",
        request_model=PairedSeriesRequest,
        compute=_r_squared,
        example=PAIRED_EXAMPLE,
        notes=(PAIRED_NOTE, "Share of asset variance explained by the benchmark (0 to 1)."),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/alpha",
        title="Alpha",
        summary="Regression alpha of excess returns",
        formulas=(
            "(r_a − rf_p) = α + β × (r_b − rf_p)  (ordinary least squares)",
            "annualized α = α × periods_per_year",
        ),
        request_model=PairedRiskFreeRequest,
        response_model=MetricBreakdownResponse,
        compute=_alpha,
        examples={"daily": {**PAIRED_EXAMPLE, "risk_free_rate": 0.05}},
        notes=(
            PAIRED_NOTE,
            "Arithmetic annualization of the intercept. For the CAPM-based alpha on annualized "
            "returns see /jensens-alpha.",
            ANNUAL_RATE_NOTE,
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
