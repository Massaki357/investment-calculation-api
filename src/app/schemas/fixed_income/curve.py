from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fixed_income.common import (
    BondPrice,
    CouponFrequency,
    CouponRate,
    FixedIncomeRequest,
    YearsToMaturity,
)


class CurveInstrumentItem(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    maturity_years: YearsToMaturity
    coupon_rate: CouponRate
    price: BondPrice
    face_value: float = Field(default=100, gt=0, description="Face value (default 100).")


class SpotCurveRequest(FixedIncomeRequest):
    instruments: list[CurveInstrumentItem] = Field(
        min_length=1,
        max_length=1200,
        description="One bond per coupon date 1/m, 2/m, ..., n/m (any order).",
    )
    coupon_frequency: CouponFrequency


class SpotPointItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    maturity_years: float
    discount_factor: float
    spot_rate: float = Field(description="Effective annual spot rate (decimal).")


class SpotCurveResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Spot Curve"
    points: list[SpotPointItem]


EffectiveSpotRate = Annotated[
    float, Field(gt=-1, description="Effective annual spot rate (decimal, > −1).")
]


class ForwardRateRequest(FixedIncomeRequest):
    short_spot_rate: EffectiveSpotRate
    short_maturity: float = Field(ge=0, le=100, description="Years (≥ 0).")
    long_spot_rate: EffectiveSpotRate
    long_maturity: float = Field(gt=0, le=100, description="Years (> short_maturity).")
