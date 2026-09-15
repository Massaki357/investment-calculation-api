from pydantic import BaseModel, ConfigDict, Field

from app.schemas.fields import RateDecimal
from app.schemas.fixed_income.common import (
    BondPrice,
    BondTermsRequest,
    BondYield,
    CouponRate,
    FaceValue,
    FixedIncomeRequest,
    YearsToMaturity,
)


class BondPriceRequest(BondTermsRequest):
    yield_to_maturity: BondYield


class BondCashFlowItem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    period: int
    time_years: float
    cash_flow: float
    discount_factor: float
    present_value: float


class BondPriceResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Bond Price"
    price: float = Field(description="Price on a coupon date (clean = dirty, no accrued interest).")
    price_to_face: float = Field(description="price / face_value (1.0 = par).")
    coupon_payment: float = Field(description="Coupon paid each period.")
    number_of_periods: int
    periodic_yield: float = Field(description="yield_to_maturity / coupon_frequency.")
    cash_flows: list[BondCashFlowItem]
    currency: str | None = None


class YieldToMaturityRequest(BondTermsRequest):
    price: BondPrice


class YieldToCallRequest(BondTermsRequest):
    price: BondPrice
    call_price: float = Field(gt=0, description="Price paid by the issuer at the call date (> 0).")
    years_to_call: YearsToMaturity


class CurrentYieldRequest(FixedIncomeRequest):
    face_value: FaceValue
    coupon_rate: CouponRate
    price: BondPrice


class DurationResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = "Duration and Convexity"
    price: float
    macaulay_duration: float = Field(description="Years.")
    modified_duration: float = Field(description="Years (≈ % price change per 1.00 yield change).")
    convexity: float = Field(description="Years².")
    currency: str | None = None


class SpreadRequest(FixedIncomeRequest):
    bond_yield: RateDecimal
    benchmark_yield: RateDecimal


class CreditSpreadRequest(BondTermsRequest):
    price: BondPrice
    risk_free_yield: BondYield
