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
    SERIES_NOTE,
    paired_returns,
    single_returns,
)
from app.schemas.common import MetricBreakdownResponse, MetricValue, Unit
from app.schemas.risk import (
    AnnualizedSeriesRequest,
    PairedAnnualizedRequest,
    PairedRiskFreeRequest,
    SharpeRequest,
    SortinoRequest,
)
from app.services.risk import performance

router = APIRouter(tags=["Risk · Risk-adjusted returns"])

PAIRED_EXAMPLE = {
    "asset_returns": RETURNS_EXAMPLE,
    "benchmark_returns": BENCHMARK_EXAMPLE,
    "risk_free_rate": 0.05,
}


def _sortino(r: SortinoRequest) -> float:
    mar = r.risk_free_rate if r.minimum_acceptable_return is None else r.minimum_acceptable_return
    return performance.sortino_ratio(single_returns(r), mar, r.periods_per_year, r.return_type)


def _treynor(r: PairedRiskFreeRequest) -> float:
    asset, benchmark = paired_returns(r)
    return performance.treynor_ratio(
        asset, benchmark, r.risk_free_rate, r.periods_per_year, r.return_type
    )


def _information_ratio(r: PairedAnnualizedRequest) -> MetricBreakdownResponse:
    asset, benchmark = paired_returns(r)
    result = performance.information_ratio(asset, benchmark, r.periods_per_year, r.return_type)
    return MetricBreakdownResponse(
        metric="Information Ratio",
        value=result.information_ratio,
        unit=Unit.NUMBER,
        components=[
            MetricValue(
                metric="Annualized Active Return",
                value=result.annualized_active_return,
                unit=Unit.DECIMAL,
            ),
            MetricValue(metric="Tracking Error", value=result.tracking_error, unit=Unit.DECIMAL),
        ],
    )


def _jensen(r: PairedRiskFreeRequest) -> MetricBreakdownResponse:
    asset, benchmark = paired_returns(r)
    result = performance.jensens_alpha(
        asset, benchmark, r.risk_free_rate, r.periods_per_year, r.return_type
    )
    return MetricBreakdownResponse(
        metric="Jensen's Alpha",
        value=result.alpha,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Beta", value=result.beta, unit=Unit.NUMBER),
            MetricValue(
                metric="Asset Annualized Return", value=result.asset_return, unit=Unit.DECIMAL
            ),
            MetricValue(
                metric="Benchmark Annualized Return",
                value=result.benchmark_return,
                unit=Unit.DECIMAL,
            ),
        ],
    )


def _m2(r: PairedRiskFreeRequest) -> MetricBreakdownResponse:
    asset, benchmark = paired_returns(r)
    result = performance.modigliani_m2(
        asset, benchmark, r.risk_free_rate, r.periods_per_year, r.return_type
    )
    return MetricBreakdownResponse(
        metric="Modigliani M²",
        value=result.m2,
        unit=Unit.DECIMAL,
        components=[
            MetricValue(metric="Sharpe Ratio", value=result.sharpe_ratio, unit=Unit.NUMBER),
            MetricValue(
                metric="Benchmark Volatility", value=result.benchmark_volatility, unit=Unit.DECIMAL
            ),
        ],
    )


METRIC_ENDPOINTS = (
    MetricEndpoint(
        path="/sharpe",
        metric="Sharpe Ratio",
        unit=Unit.NUMBER,
        summary="Annualized Sharpe ratio",
        formula="Sharpe = mean(r − rf_p) / σ(r − rf_p) × √periods_per_year",
        request_model=SharpeRequest,
        compute=lambda r: performance.sharpe_ratio(
            single_returns(r), r.risk_free_rate, r.periods_per_year, r.return_type
        ),
        example={"returns": RETURNS_EXAMPLE, "risk_free_rate": 0.05},
        notes=(SERIES_NOTE, "Sample σ.", ANNUAL_RATE_NOTE),
    ),
    MetricEndpoint(
        path="/sortino",
        metric="Sortino Ratio",
        unit=Unit.NUMBER,
        summary="Annualized Sortino ratio",
        formula="Sortino = mean(r − MAR_p) / DD × √periods_per_year, "
        "DD = √(Σ min(r − MAR_p, 0)² / N)",
        request_model=SortinoRequest,
        compute=_sortino,
        example={"returns": RETURNS_EXAMPLE, "risk_free_rate": 0.05},
        notes=(
            SERIES_NOTE,
            "minimum_acceptable_return defaults to risk_free_rate; N counts all observations.",
            ANNUAL_RATE_NOTE,
        ),
    ),
    MetricEndpoint(
        path="/treynor",
        metric="Treynor Ratio",
        unit=Unit.NUMBER,
        summary="Treynor ratio",
        formula="Treynor = (annualized asset return − risk_free_rate) / β",
        request_model=PairedRiskFreeRequest,
        compute=_treynor,
        example=PAIRED_EXAMPLE,
        notes=(PAIRED_NOTE, "Geometric annualized return; β from the same series."),
    ),
    MetricEndpoint(
        path="/calmar",
        metric="Calmar Ratio",
        unit=Unit.NUMBER,
        summary="Calmar ratio",
        formula="Calmar = annualized return / |maximum drawdown|",
        request_model=AnnualizedSeriesRequest,
        compute=lambda r: performance.calmar_ratio(
            single_returns(r), r.periods_per_year, r.return_type
        ),
        example={"returns": RETURNS_EXAMPLE},
        notes=(
            SERIES_NOTE,
            "Uses the whole series (not a fixed 36-month window). No drawdown returns "
            "DIVISION_BY_ZERO.",
        ),
    ),
)

CALCULATION_ENDPOINTS = (
    CalculationEndpoint(
        path="/information-ratio",
        title="Information Ratio",
        summary="Information ratio against a benchmark",
        formulas=(
            "active_t = r_asset,t − r_benchmark,t",
            "IR = mean(active) × ppy / (σ(active) × √ppy)",
        ),
        request_model=PairedAnnualizedRequest,
        response_model=MetricBreakdownResponse,
        compute=_information_ratio,
        examples={
            "daily": {"asset_returns": RETURNS_EXAMPLE, "benchmark_returns": BENCHMARK_EXAMPLE}
        },
        notes=(PAIRED_NOTE, "Tracking error is the annualized sample σ of active returns."),
    ),
    CalculationEndpoint(
        path="/jensens-alpha",
        title="Jensen's Alpha",
        summary="Jensen's alpha (CAPM alpha on annualized returns)",
        formulas=("α = R_p − [rf + β × (R_m − rf)]",),
        request_model=PairedRiskFreeRequest,
        response_model=MetricBreakdownResponse,
        compute=_jensen,
        examples={"daily": PAIRED_EXAMPLE},
        notes=(
            PAIRED_NOTE,
            "R_p and R_m are geometric annualized returns; rf is annual.",
        ),
    ),
    CalculationEndpoint(
        path="/m2",
        title="Modigliani M²",
        summary="Modigliani risk-adjusted performance (M²)",
        formulas=("M² = Sharpe_p × σ_benchmark + rf",),
        request_model=PairedRiskFreeRequest,
        response_model=MetricBreakdownResponse,
        compute=_m2,
        examples={"daily": PAIRED_EXAMPLE},
        notes=(
            PAIRED_NOTE,
            "Annualized Sharpe ratio of the asset and annualized benchmark volatility.",
            ANNUAL_RATE_NOTE,
        ),
    ),
)

add_metric_endpoints(router, METRIC_ENDPOINTS)
add_calculation_endpoints(router, CALCULATION_ENDPOINTS)
