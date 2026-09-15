from typing import Annotated

from pydantic import Field

from app.schemas.common import MonetaryRequest


class FixedIncomeRequest(MonetaryRequest):
    """Base for every fixed income request (all accept an optional informational `currency`)."""


AnnualRate = Annotated[
    float, Field(description="Annual rate in decimal form (0.12 = 12% per year).")
]
Years = Annotated[
    float, Field(ge=0, le=1000, description="Time in years (≥ 0, fractions allowed).")
]
CompoundingFrequency = Annotated[
    int,
    Field(
        ge=1,
        le=365,
        description="Compounding periods per year (1 annual, 2 semiannual, 12 "
        "monthly, 252 or 365 daily).",
    ),
]

FaceValue = Annotated[float, Field(gt=0, description="Face (par) value repaid at maturity (> 0).")]
CouponRate = Annotated[
    float, Field(ge=0, description="Annual coupon rate in decimal form (0.06 = 6%), ≥ 0.")
]
YearsToMaturity = Annotated[
    float,
    Field(
        gt=0,
        le=100,
        description="Years to maturity. years_to_maturity × coupon_frequency must be a whole "
        "number (pricing on a coupon date).",
    ),
]
CouponFrequency = Annotated[
    int, Field(ge=1, le=12, description="Coupon payments per year (1, 2, 4 or 12).")
]
BondYield = Annotated[
    float,
    Field(
        description="Annual yield in decimal form, compounded at coupon_frequency "
        "(bond-equivalent: periodic yield = yield / coupon_frequency)."
    ),
]
BondPrice = Annotated[
    float, Field(gt=0, description="Bond price in the same currency units as face_value (> 0).")
]


class BondTermsRequest(FixedIncomeRequest):
    face_value: FaceValue
    coupon_rate: CouponRate
    years_to_maturity: YearsToMaturity
    coupon_frequency: CouponFrequency
