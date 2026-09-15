"""Request and response models for technical analysis indicators."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import BaseRequest

Prices = Annotated[
    list[Annotated[float, Field(gt=0)]],
    Field(min_length=1, description="Prices (> 0) in chronological order, oldest first."),
]
Volumes = Annotated[
    list[Annotated[float, Field(ge=0)]],
    Field(min_length=1, description="Traded volume (≥ 0) per period, aligned with prices."),
]
Period = Annotated[int, Field(ge=1, le=1000, description="Look-back window in periods.")]


class PriceSeriesRequest(BaseRequest):
    prices: Prices


class AverageRequest(PriceSeriesRequest):
    period: Period = 20


class VwmaRequest(AverageRequest):
    volumes: Volumes


class RsiRequest(PriceSeriesRequest):
    period: Period = 14


class RocRequest(PriceSeriesRequest):
    period: Period = 12


class MacdRequest(PriceSeriesRequest):
    fast_period: Period = 12
    slow_period: Period = 26
    signal_period: Period = 9


class BollingerRequest(PriceSeriesRequest):
    period: Period = 20
    standard_deviations: float = Field(
        default=2.0, gt=0, le=10, description="Band width in standard deviations (k)."
    )


class HistoricalVolatilityRequest(PriceSeriesRequest):
    period: int = Field(default=20, ge=2, le=1000, description="Number of log returns per window.")
    periods_per_year: int = Field(default=252, ge=1, le=366, description="Annualization factor.")


class HlcRequest(BaseRequest):
    high: Prices
    low: Prices
    close: Prices


class StochasticRequest(HlcRequest):
    k_period: Period = 14
    d_period: Period = 3


class WilliamsRRequest(HlcRequest):
    period: Period = 14


class CciRequest(HlcRequest):
    period: Period = 20


class AtrRequest(HlcRequest):
    period: Period = 14


class ObvRequest(BaseRequest):
    close: Prices
    volumes: Volumes


class VwapRequest(BaseRequest):
    prices: Prices | None = Field(
        default=None, description="Price per period (e.g. close). Alternative to high/low/close."
    )
    high: Prices | None = None
    low: Prices | None = None
    close: Prices | None = None
    volumes: Volumes

    @model_validator(mode="after")
    def _price_source(self) -> Self:
        bars = (self.high, self.low, self.close)
        if self.prices is not None and any(item is not None for item in bars):
            raise ValueError("send prices, or high/low/close, not both")
        if self.prices is None and any(item is None for item in bars):
            raise ValueError("send prices, or all of high, low and close")
        return self


class MfiRequest(HlcRequest):
    volumes: Volumes
    period: Period = 14


# --- Responses ---------------------------------------------------------------------------------

IndicatorSeries = Annotated[
    list[float | None],
    Field(description="Same length as the input; null during warm-up or where undefined."),
]


class _Response(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str
    parameters: dict[str, int | float] = Field(description="Parameters used in the calculation.")


class IndicatorResponse(_Response):
    values: IndicatorSeries
    latest: float | None = Field(description="Last value of the series (null if undefined).")


class MacdResponse(_Response):
    macd: IndicatorSeries
    signal: IndicatorSeries
    histogram: IndicatorSeries
    latest: dict[str, float | None]


class StochasticResponse(_Response):
    percent_k: IndicatorSeries
    percent_d: IndicatorSeries
    latest: dict[str, float | None]


class BollingerResponse(_Response):
    middle: IndicatorSeries
    upper: IndicatorSeries
    lower: IndicatorSeries
    percent_b: IndicatorSeries = Field(description="(P − lower) / (upper − lower).")
    bandwidth: IndicatorSeries = Field(description="(upper − lower) / middle.")
    latest: dict[str, float | None]
