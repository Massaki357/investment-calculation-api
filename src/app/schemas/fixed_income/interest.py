from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.fixed_income.common import (
    AnnualRate,
    CompoundingFrequency,
    FixedIncomeRequest,
    Years,
)


class Compounding(StrEnum):
    SIMPLE = "simple"
    PERIODIC = "periodic"
    CONTINUOUS = "continuous"


class RateCompounding(StrEnum):
    PERIODIC = "periodic"
    CONTINUOUS = "continuous"


COMPOUNDING_DESCRIPTION = (
    "simple: 1 + rate × years · periodic (default): (1 + rate / m)^(m × years) · "
    "continuous: e^(rate × years)."
)


class SimpleInterestRequest(FixedIncomeRequest):
    principal: float = Field(description="Initial amount.")
    rate: AnnualRate
    years: Years


class CompoundInterestRequest(FixedIncomeRequest):
    principal: float = Field(description="Initial amount.")
    rate: AnnualRate
    years: Years
    compounding: RateCompounding = Field(
        default=RateCompounding.PERIODIC,
        description="periodic (default): (1 + rate / m)^(m × years) · "
        "continuous: e^(rate × years).",
    )
    compounding_frequency: CompoundingFrequency = 1


class _TimeValueRequest(FixedIncomeRequest):
    rate: AnnualRate
    years: Years
    compounding: Compounding = Field(
        default=Compounding.PERIODIC, description=COMPOUNDING_DESCRIPTION
    )
    compounding_frequency: CompoundingFrequency = Field(
        default=1, description="Used only with periodic compounding (default 1 = annual)."
    )


class FutureValueRequest(_TimeValueRequest):
    present_value: float = Field(description="Amount today.")


class PresentValueRequest(_TimeValueRequest):
    future_value: float = Field(description="Amount at the end of the horizon.")


class InterestResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str
    principal: float
    interest: float = Field(description="future_value − principal (amount).")
    future_value: float
    currency: str | None = None


# --- Rates ---------------------------------------------------------------------------------


class NominalRateRequest(FixedIncomeRequest):
    effective_rate: float = Field(gt=-1, description="Effective annual rate (decimal, > −1).")
    compounding_frequency: CompoundingFrequency


class EffectiveRateRequest(FixedIncomeRequest):
    nominal_rate: AnnualRate
    compounding: RateCompounding = Field(default=RateCompounding.PERIODIC)
    compounding_frequency: CompoundingFrequency | None = Field(
        default=None, description="Required for periodic compounding; not allowed for continuous."
    )

    @model_validator(mode="after")
    def _frequency_matches_compounding(self) -> Self:
        if self.compounding is RateCompounding.PERIODIC and self.compounding_frequency is None:
            raise ValueError("periodic compounding requires compounding_frequency")
        if (
            self.compounding is RateCompounding.CONTINUOUS
            and self.compounding_frequency is not None
        ):
            raise ValueError("continuous compounding does not use compounding_frequency")
        return self


class RealRateMethod(StrEnum):
    EXACT = "exact"
    APPROXIMATE = "approximate"


class RealRateRequest(FixedIncomeRequest):
    nominal_rate: float = Field(description="Nominal rate for the period (decimal).")
    inflation_rate: float = Field(gt=-1, description="Inflation for the same period (decimal).")
    method: RealRateMethod = Field(
        default=RealRateMethod.EXACT,
        description="exact (default): (1 + nominal) / (1 + inflation) − 1 · "
        "approximate: nominal − inflation.",
    )


class RatePeriod(StrEnum):
    DAY = "day"
    BUSINESS_DAY = "business_day"
    MONTH = "month"
    QUARTER = "quarter"
    SEMESTER = "semester"
    YEAR = "year"


class RateConversionRequest(FixedIncomeRequest):
    rate: float = Field(gt=-1, description="Effective rate for from_period (decimal, > −1).")
    from_period: RatePeriod
    to_period: RatePeriod
    days_per_year: int = Field(
        default=365, description="Calendar days per year for 'day' periods (360 or 365)."
    )
    business_days_per_year: int = Field(
        default=252, ge=1, le=366, description="Business days per year for 'business_day' (252)."
    )

    @model_validator(mode="after")
    def _supported_day_count(self) -> Self:
        if self.days_per_year not in (360, 365):
            raise ValueError("days_per_year must be 360 or 365")
        return self
