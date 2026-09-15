"""Request and response models for risk and risk-adjusted performance endpoints."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import BaseRequest
from app.schemas.validators import require_exactly_one
from app.services.risk.returns import ReturnType

ReturnSeries = Annotated[
    list[float],
    Field(
        min_length=2,
        description="Periodic returns in decimal form (0.01 = 1%), chronological order, ≥ 2 items.",
    ),
]
PriceSeries = Annotated[
    list[Annotated[float, Field(gt=0)]],
    Field(min_length=3, description="Prices (> 0) in chronological order, ≥ 3 items."),
]
PeriodsPerYear = Annotated[
    int,
    Field(
        ge=1,
        le=366,
        description="Return periods per year: 252 daily (default), 52 weekly, 12 monthly.",
    ),
]
AnnualRate = Annotated[
    float, Field(gt=-1, description="Annual rate in decimal form (0.10 = 10%), > −1.")
]
Confidence = Annotated[
    float, Field(gt=0.5, lt=1, description="Confidence level in (0.5, 1), e.g. 0.95 or 0.99.")
]
RETURN_TYPE_DESCRIPTION = (
    "simple (default): P_t / P_{t−1} − 1 · log: ln(P_t / P_{t−1}). "
    "Describes the returns sent, or how prices are converted."
)


class _SingleSeries(BaseRequest):
    returns: ReturnSeries | None = None
    prices: PriceSeries | None = None
    return_type: ReturnType = Field(default=ReturnType.SIMPLE, description=RETURN_TYPE_DESCRIPTION)

    @model_validator(mode="after")
    def _one_series(self) -> Self:
        require_exactly_one(self, "returns", "prices")
        return self


class SeriesRequest(_SingleSeries):
    """Send `returns` or `prices` (not both)."""


class PricesToReturnsRequest(BaseRequest):
    prices: Annotated[
        list[Annotated[float, Field(gt=0)]],
        Field(min_length=2, description="Prices (> 0) in chronological order, ≥ 2 items."),
    ]
    return_type: ReturnType = Field(default=ReturnType.SIMPLE, description=RETURN_TYPE_DESCRIPTION)


class AnnualizedSeriesRequest(_SingleSeries):
    periods_per_year: PeriodsPerYear = 252


class DispersionRequest(AnnualizedSeriesRequest):
    population: bool = Field(default=False, description="Population (ddof = 0) instead of sample.")


class DownsideDeviationRequest(AnnualizedSeriesRequest):
    minimum_acceptable_return: AnnualRate = 0


class SharpeRequest(AnnualizedSeriesRequest):
    risk_free_rate: AnnualRate = 0


class SortinoRequest(AnnualizedSeriesRequest):
    risk_free_rate: AnnualRate = 0
    minimum_acceptable_return: AnnualRate | None = Field(
        default=None, description="Annual MAR; defaults to risk_free_rate."
    )


class TailRiskRequest(_SingleSeries):
    confidence: Confidence = 0.95
    horizon_periods: int = Field(
        default=1, ge=1, le=10_000, description="Horizon in return periods (√h scaling)."
    )


class ParametricVarRequest(TailRiskRequest):
    include_mean: bool = Field(default=True, description="Include the mean return in the VaR.")


class TailMethod(StrEnum):
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"


class ExpectedShortfallRequest(TailRiskRequest):
    method: TailMethod = Field(default=TailMethod.HISTORICAL)
    include_mean: bool = Field(default=True, description="Parametric method only.")


class _PairedSeries(BaseRequest):
    asset_returns: ReturnSeries | None = None
    asset_prices: PriceSeries | None = None
    benchmark_returns: ReturnSeries | None = None
    benchmark_prices: PriceSeries | None = None
    return_type: ReturnType = Field(default=ReturnType.SIMPLE, description=RETURN_TYPE_DESCRIPTION)

    @model_validator(mode="after")
    def _one_series_per_side(self) -> Self:
        require_exactly_one(self, "asset_returns", "asset_prices")
        require_exactly_one(self, "benchmark_returns", "benchmark_prices")
        return self


class PairedSeriesRequest(_PairedSeries):
    """Send asset_returns or asset_prices, and benchmark_returns or benchmark_prices."""


class PairedCovarianceRequest(_PairedSeries):
    population: bool = Field(default=False, description="Population (ddof = 0) instead of sample.")


class PairedAnnualizedRequest(_PairedSeries):
    periods_per_year: PeriodsPerYear = 252


class PairedRiskFreeRequest(PairedAnnualizedRequest):
    risk_free_rate: AnnualRate = 0


class ReturnsResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Returns"
    return_type: ReturnType
    observations: int
    returns: list[float]


class DrawdownResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Maximum Drawdown"
    max_drawdown: float = Field(
        description="Worst peak-to-trough decline, negative decimal (0 = none)."
    )
    peak_index: int | None = Field(
        description="Index of the peak (null when there is no drawdown)."
    )
    trough_index: int | None
    recovery_index: int | None = Field(description="First index back at the peak; null if never.")
    duration_periods: int | None = Field(description="trough_index − peak_index.")
