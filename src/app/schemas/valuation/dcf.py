from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fields import (
    CashFlowSeries,
    DiscountRate,
    GrowthRate,
    SharePrice,
    SharesOutstanding,
)
from app.schemas.validators import require_fields
from app.schemas.valuation.common import ValuationRequest

MID_YEAR_DESCRIPTION = (
    "When true, cash flow i is discounted at i − 0.5 instead of i. "
    "The terminal value is still discounted from the end of the last period."
)


# --- Time value ---------------------------------------------------------------------------


class PresentValueRequest(ValuationRequest):
    cash_flows: CashFlowSeries
    discount_rate: DiscountRate
    periods: list[Annotated[float, Field(ge=0)]] | None = Field(
        default=None,
        description="Optional timing of each cash flow in periods (≥ 0, fractions allowed). "
        "Defaults to 1, 2, ..., n.",
    )
    mid_year_convention: bool = Field(default=False, description=MID_YEAR_DESCRIPTION)

    @model_validator(mode="after")
    def _timing_is_consistent(self) -> Self:
        if self.periods is not None:
            if self.mid_year_convention:
                raise ValueError("send either periods or mid_year_convention, not both")
            if len(self.periods) != len(self.cash_flows):
                raise ValueError("periods must have the same length as cash_flows")
        return self


class DiscountedCashFlowItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    period: float = Field(description="Time of the cash flow in periods.")
    cash_flow: float
    discount_factor: float = Field(description="1 / (1 + rate) ^ period.")
    present_value: float


class PresentValueResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: Literal["Present Value"] = "Present Value"
    present_value: float = Field(description="Sum of the discounted cash flows (amount).")
    discounted_cash_flows: list[DiscountedCashFlowItem]
    currency: str | None = None


class FutureValueRequest(ValuationRequest):
    present_value: float = Field(description="Amount today.")
    rate: GrowthRate
    periods: float = Field(ge=0, description="Number of compounding periods (≥ 0).")


# --- Terminal value, EV, equity -----------------------------------------------------------


class PerpetuityGrowthTerminalValueRequest(ValuationRequest):
    final_cash_flow: float = Field(description="Cash flow of the last explicit period (n).")
    discount_rate: DiscountRate
    growth_rate: GrowthRate


class ExitMultipleTerminalValueRequest(ValuationRequest):
    terminal_metric: float = Field(
        description="Metric of the last explicit period the multiple applies to (e.g. EBITDA_n)."
    )
    multiple: float = Field(description="Exit multiple (e.g. EV/EBITDA of 8.0).")


class EnterpriseValueRequest(ValuationRequest):
    present_value_of_cash_flows: float = Field(description="Σ PV of explicit FCFF.")
    present_value_of_terminal_value: float = Field(description="PV of the terminal value.")


class EquityValueRequest(ValuationRequest):
    enterprise_value: float
    net_debt: float = Field(description="Net debt; negative means net cash.")
    minority_interest: float = Field(default=0, ge=0, description="Non-controlling interests.")
    non_operating_assets: float = Field(
        default=0, ge=0, description="Non-operating assets not captured by the cash flows."
    )


class ValuePerShareRequest(ValuationRequest):
    equity_value: float
    shares_outstanding: SharesOutstanding


class MarginOfSafetyRequest(ValuationRequest):
    intrinsic_value: float = Field(description="Estimated intrinsic value per share (≠ 0).")
    market_price: SharePrice


# --- Full DCF ------------------------------------------------------------------------------


class PerpetuityGrowthTerminal(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    method: Literal["perpetuity_growth"]
    growth_rate: GrowthRate


class ExitMultipleTerminal(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    method: Literal["exit_multiple"]
    terminal_metric: float = Field(description="Metric of year n (e.g. EBITDA_n).")
    multiple: float = Field(description="Exit multiple applied to terminal_metric.")


TerminalAssumption = Annotated[
    PerpetuityGrowthTerminal | ExitMultipleTerminal,
    Field(
        discriminator="method",
        description="perpetuity_growth: TV = CF_n × (1 + g) / (r − g). "
        "exit_multiple: TV = terminal_metric × multiple.",
    ),
]


class _DcfRequestBase(ValuationRequest):
    cash_flows: CashFlowSeries
    terminal: TerminalAssumption
    mid_year_convention: bool = Field(default=False, description=MID_YEAR_DESCRIPTION)
    shares_outstanding: SharesOutstanding | None = None
    share_price: SharePrice | None = Field(
        default=None, description="Current market price; enables margin_of_safety."
    )

    @model_validator(mode="after")
    def _price_requires_shares(self) -> Self:
        if self.share_price is not None:
            require_fields(self, "share_price", "shares_outstanding")
        return self


class FcffDcfRequest(_DcfRequestBase):
    discount_rate: DiscountRate = Field(description="WACC in decimal form (0.10 = 10%).")
    net_debt: float = Field(description="Net debt; negative means net cash.")
    minority_interest: float = Field(default=0, ge=0)
    non_operating_assets: float = Field(default=0, ge=0)


class FcfeDcfRequest(_DcfRequestBase):
    cost_of_equity: DiscountRate


TerminalValueField = Annotated[
    float, Field(description="Undiscounted terminal value at the end of period n.")
]
TerminalPercentageField = Annotated[
    float | None,
    Field(description="PV of terminal value / total value (decimal). Null when total value is 0."),
]
ValuePerShareField = Annotated[
    float | None, Field(description="Null when shares_outstanding is absent.")
]
MarginOfSafetyField = Annotated[
    float | None,
    Field(
        description="(value_per_share − share_price) / value_per_share. "
        "Null without share_price or when value_per_share ≤ 0."
    ),
]


class FcffDcfResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: Literal["DCF (FCFF)"] = "DCF (FCFF)"
    enterprise_value: float = Field(description="Σ PV(FCFF) + PV(terminal value).")
    equity_value: float
    terminal_value: TerminalValueField
    terminal_value_percentage: TerminalPercentageField
    value_per_share: ValuePerShareField
    margin_of_safety: MarginOfSafetyField
    present_value_of_cash_flows: float
    present_value_of_terminal_value: float
    discounted_cash_flows: list[DiscountedCashFlowItem]
    currency: str | None = None


class FcfeDcfResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: Literal["DCF (FCFE)"] = "DCF (FCFE)"
    equity_value: float = Field(description="Σ PV(FCFE) + PV(terminal value).")
    terminal_value: TerminalValueField
    terminal_value_percentage: TerminalPercentageField
    value_per_share: ValuePerShareField
    margin_of_safety: MarginOfSafetyField
    present_value_of_cash_flows: float
    present_value_of_terminal_value: float
    discounted_cash_flows: list[DiscountedCashFlowItem]
    currency: str | None = None
