from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fields import DiscountRate, GrowthRate
from app.schemas.validators import require_exactly_one
from app.schemas.valuation.common import ValuationRequest

DividendSeries = Annotated[
    list[float],
    Field(
        min_length=1,
        max_length=1000,
        description="Dividends per share for periods 1..n, in chronological order.",
    ),
]
Years = Annotated[int, Field(ge=1, le=100, description="Number of years (1 to 100).")]
CurrentDividend = Annotated[
    float, Field(ge=0, description="Most recent dividend per share, D0 (≥ 0).")
]


class DdmRequest(ValuationRequest):
    dividends: DividendSeries
    cost_of_equity: DiscountRate
    terminal_price: float = Field(
        default=0, ge=0, description="Expected price at the end of period n (default 0)."
    )


class GordonGrowthRequest(ValuationRequest):
    next_dividend: float | None = Field(
        default=None, ge=0, description="D1: dividend expected next period."
    )
    current_dividend: float | None = Field(
        default=None, ge=0, description="D0: current dividend; D1 = D0 × (1 + g)."
    )
    cost_of_equity: DiscountRate
    growth_rate: GrowthRate

    @model_validator(mode="after")
    def _one_dividend(self) -> Self:
        require_exactly_one(self, "next_dividend", "current_dividend")
        return self


class TwoStageDdmRequest(ValuationRequest):
    current_dividend: CurrentDividend
    high_growth_rate: GrowthRate
    high_growth_years: Years
    stable_growth_rate: GrowthRate
    cost_of_equity: DiscountRate
    stable_cost_of_equity: DiscountRate | None = Field(
        default=None,
        description="Cost of equity in the stable stage (used in the terminal price). "
        "Defaults to cost_of_equity.",
    )


class ThreeStageDdmRequest(TwoStageDdmRequest):
    transition_years: Years


class DividendProjectionItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    period: int
    stage: Literal["high_growth", "transition"]
    growth_rate: float
    dividend: float
    discount_factor: float
    present_value: float


class MultiStageDdmResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str
    value: float = Field(description="Intrinsic value per share (amount).")
    present_value_of_dividends: float
    terminal_dividend: float = Field(description="First dividend of the stable stage.")
    terminal_value: float = Field(description="Price at the end of the explicit horizon.")
    present_value_of_terminal_value: float
    terminal_value_percentage: float | None = Field(
        description="PV of terminal value / value (decimal). Null when value is 0."
    )
    projections: list[DividendProjectionItem]
    currency: str | None = None
