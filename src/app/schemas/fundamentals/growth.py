from pydantic import Field

from app.schemas.fields import TaxRate
from app.schemas.fundamentals.common import (
    CapitalExpenditures,
    ChangeInWorkingCapital,
    DepreciationAmortization,
    Ebit,
    FundamentalsRequest,
    NetIncome,
)


class GrowthRequest(FundamentalsRequest):
    current_value: float = Field(description="Value in the current period.")
    previous_value: float = Field(description="Value in the previous period (≠ 0).")


class CagrRequest(FundamentalsRequest):
    beginning_value: float = Field(description="Value at the start (must be > 0 for CAGR).")
    ending_value: float = Field(description="Value at the end (must be > 0 for CAGR).")
    years: float = Field(gt=0, description="Elapsed time in years (> 0, fractions allowed).")


class SustainableGrowthRequest(FundamentalsRequest):
    return_on_equity: float = Field(description="ROE in decimal form (0.18 = 18%).")
    retention_ratio: float = Field(description="Share of earnings retained, decimal (0.60 = 60%).")


class RetentionRatioRequest(FundamentalsRequest):
    net_income: NetIncome
    dividends_paid: float = Field(ge=0, description="Dividends paid, positive magnitude (≥ 0).")


class ReinvestmentRateRequest(FundamentalsRequest):
    capital_expenditures: CapitalExpenditures
    depreciation_amortization: DepreciationAmortization
    change_in_working_capital: ChangeInWorkingCapital
    ebit: Ebit
    tax_rate: TaxRate
