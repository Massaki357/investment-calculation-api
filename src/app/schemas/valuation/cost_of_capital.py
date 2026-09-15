from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from app.schemas.common import MetricResponse, MetricValue
from app.schemas.fields import Beta, RateDecimal, TaxRate
from app.schemas.validators import require_exactly_one, require_fields
from app.schemas.valuation.common import ValuationRequest

DebtToEquity = Annotated[
    float, Field(ge=0, description="Debt-to-equity ratio D/E (≥ 0), preferably market values.")
]


class _MarketPremiumMixin(ValuationRequest):
    risk_free_rate: RateDecimal
    beta: Beta
    market_risk_premium: RateDecimal | None = Field(
        default=None, description="Equity/market risk premium (decimal)."
    )
    expected_market_return: RateDecimal | None = Field(
        default=None, description="Expected market return; premium = this − risk_free_rate."
    )

    @model_validator(mode="after")
    def _one_premium_source(self) -> Self:
        require_exactly_one(self, "market_risk_premium", "expected_market_return")
        return self


class CapmRequest(_MarketPremiumMixin):
    pass


class CostOfEquityRequest(_MarketPremiumMixin):
    country_risk_premium: RateDecimal = 0
    size_premium: RateDecimal = 0
    specific_risk_premium: RateDecimal = 0


class LeveredBetaRequest(ValuationRequest):
    unlevered_beta: Beta
    tax_rate: TaxRate
    debt_to_equity: DebtToEquity


class UnleveredBetaRequest(ValuationRequest):
    levered_beta: Beta
    tax_rate: TaxRate
    debt_to_equity: DebtToEquity


class CostOfDebtMethod(StrEnum):
    RISK_FREE_PLUS_SPREAD = "risk_free_plus_spread"
    INTEREST_OVER_DEBT = "interest_over_debt"


class CostOfDebtRequest(ValuationRequest):
    method: CostOfDebtMethod = Field(
        default=CostOfDebtMethod.RISK_FREE_PLUS_SPREAD,
        description="risk_free_plus_spread (default): rf + credit_spread. "
        "interest_over_debt: interest_expense / total_debt.",
    )
    risk_free_rate: RateDecimal | None = None
    credit_spread: RateDecimal | None = None
    interest_expense: float | None = Field(default=None, ge=0)
    total_debt: float | None = Field(
        default=None, ge=0, description="Interest-bearing debt (average of the period recommended)."
    )

    @model_validator(mode="after")
    def _method_fields(self) -> Self:
        if self.method is CostOfDebtMethod.RISK_FREE_PLUS_SPREAD:
            require_fields(self, f"method '{self.method.value}'", "risk_free_rate", "credit_spread")
        else:
            require_fields(self, f"method '{self.method.value}'", "interest_expense", "total_debt")
        return self


class AfterTaxCostOfDebtRequest(ValuationRequest):
    pre_tax_cost_of_debt: RateDecimal
    tax_rate: TaxRate


class WaccRequest(ValuationRequest):
    equity_value: float = Field(ge=0, description="Market value of equity (≥ 0).")
    debt_value: float = Field(ge=0, description="Market value of interest-bearing debt (≥ 0).")
    cost_of_equity: RateDecimal
    pre_tax_cost_of_debt: RateDecimal
    tax_rate: TaxRate


class WaccResponse(MetricResponse):
    components: list[MetricValue] = Field(
        description="Capital weights and component costs used in the calculation."
    )
