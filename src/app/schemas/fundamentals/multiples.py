from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from app.schemas.fields import SharePrice
from app.schemas.fundamentals.common import (
    BookValuePerShare,
    EarningsPerShare,
    Ebit,
    Ebitda,
    EnterpriseValue,
    FreeCashFlow,
    FundamentalsRequest,
    GrowthRateDecimal,
    MarketCapitalization,
    Revenue,
)


class PriceToEarningsRequest(FundamentalsRequest):
    share_price: SharePrice
    earnings_per_share: EarningsPerShare


class PriceToBookRequest(FundamentalsRequest):
    share_price: SharePrice
    book_value_per_share: BookValuePerShare


class PriceToSalesRequest(FundamentalsRequest):
    market_capitalization: MarketCapitalization
    revenue: Revenue


class EvToEbitdaRequest(FundamentalsRequest):
    enterprise_value: EnterpriseValue
    ebitda: Ebitda


class EvToEbitRequest(FundamentalsRequest):
    enterprise_value: EnterpriseValue
    ebit: Ebit


class EvToRevenueRequest(FundamentalsRequest):
    enterprise_value: EnterpriseValue
    revenue: Revenue


class EvToFreeCashFlowRequest(FundamentalsRequest):
    enterprise_value: EnterpriseValue
    free_cash_flow: FreeCashFlow


class EarningsYieldMethod(StrEnum):
    EARNINGS_TO_PRICE = "earnings_to_price"
    EBIT_TO_ENTERPRISE_VALUE = "ebit_to_enterprise_value"


class EarningsYieldRequest(FundamentalsRequest):
    method: EarningsYieldMethod = Field(
        default=EarningsYieldMethod.EARNINGS_TO_PRICE,
        description="earnings_to_price (default): EPS / price. "
        "ebit_to_enterprise_value (Greenblatt): EBIT / EV.",
    )
    earnings_per_share: EarningsPerShare | None = None
    share_price: SharePrice | None = None
    ebit: Ebit | None = None
    enterprise_value: EnterpriseValue | None = None

    @model_validator(mode="after")
    def _require_method_fields(self) -> Self:
        required = {
            EarningsYieldMethod.EARNINGS_TO_PRICE: ("earnings_per_share", "share_price"),
            EarningsYieldMethod.EBIT_TO_ENTERPRISE_VALUE: ("ebit", "enterprise_value"),
        }[self.method]
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise ValueError(f"method '{self.method.value}' requires: {', '.join(missing)}")
        return self


class FreeCashFlowYieldRequest(FundamentalsRequest):
    free_cash_flow: FreeCashFlow
    market_capitalization: MarketCapitalization


class EbitdaYieldRequest(FundamentalsRequest):
    ebitda: Ebitda
    enterprise_value: EnterpriseValue


class PegRatioRequest(FundamentalsRequest):
    pe_ratio: float = Field(description="Price/earnings multiple.")
    earnings_growth_rate: GrowthRateDecimal
