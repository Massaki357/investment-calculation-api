from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import MetricValue
from app.schemas.fields import TaxRate
from app.schemas.fundamentals.common import (
    CashAndEquivalents,
    CurrentLiabilities,
    Ebit,
    Ebitda,
    FreeCashFlow,
    FundamentalsRequest,
    GrossDebt,
    GrossProfit,
    InvestedCapitalBalance,
    NetIncome,
    PretaxIncome,
    Revenue,
    ShareholdersEquityBalance,
    TotalAssetsBalance,
)


class ReturnOnEquityRequest(FundamentalsRequest):
    net_income: NetIncome
    shareholders_equity: ShareholdersEquityBalance


class ReturnOnAssetsRequest(FundamentalsRequest):
    net_income: NetIncome
    total_assets: TotalAssetsBalance


class ReturnOnInvestedCapitalRequest(FundamentalsRequest):
    """Send `invested_capital` directly, or all of total_debt, shareholders_equity and cash."""

    ebit: Ebit
    tax_rate: TaxRate
    invested_capital: InvestedCapitalBalance | None = None
    total_debt: GrossDebt | None = None
    shareholders_equity: float | None = Field(
        default=None, description="Shareholders' equity (component mode)."
    )
    cash_and_equivalents: CashAndEquivalents | None = None

    @model_validator(mode="after")
    def _one_invested_capital_source(self) -> Self:
        components = (self.total_debt, self.shareholders_equity, self.cash_and_equivalents)
        has_direct = self.invested_capital is not None
        provided = sum(value is not None for value in components)
        if has_direct and provided:
            raise ValueError(
                "send either invested_capital or its components "
                "(total_debt, shareholders_equity, cash_and_equivalents), not both"
            )
        if not has_direct and provided != len(components):
            raise ValueError(
                "send invested_capital, or all of total_debt, shareholders_equity "
                "and cash_and_equivalents"
            )
        return self


class ReturnOnCapitalEmployedRequest(FundamentalsRequest):
    ebit: Ebit
    total_assets: float = Field(ge=0, description="Total assets (≥ 0).")
    current_liabilities: CurrentLiabilities


class GrossMarginRequest(FundamentalsRequest):
    gross_profit: GrossProfit
    revenue: Revenue


class EbitdaMarginRequest(FundamentalsRequest):
    ebitda: Ebitda
    revenue: Revenue


class EbitMarginRequest(FundamentalsRequest):
    ebit: Ebit
    revenue: Revenue


class NetMarginRequest(FundamentalsRequest):
    net_income: NetIncome
    revenue: Revenue


class FreeCashFlowMarginRequest(FundamentalsRequest):
    free_cash_flow: FreeCashFlow
    revenue: Revenue


class AssetTurnoverRequest(FundamentalsRequest):
    revenue: Revenue
    total_assets: TotalAssetsBalance


class DuPontMethod(StrEnum):
    THREE_FACTOR = "three_factor"
    FIVE_FACTOR = "five_factor"


class DuPontRequest(FundamentalsRequest):
    method: DuPontMethod = Field(
        default=DuPontMethod.THREE_FACTOR,
        description="three_factor (default) or five_factor (requires pretax_income and ebit).",
    )
    net_income: NetIncome
    revenue: Revenue
    total_assets: TotalAssetsBalance
    shareholders_equity: ShareholdersEquityBalance
    pretax_income: PretaxIncome | None = None
    ebit: Ebit | None = None

    @model_validator(mode="after")
    def _five_factor_fields(self) -> Self:
        if self.method is DuPontMethod.FIVE_FACTOR:
            missing = [n for n in ("pretax_income", "ebit") if getattr(self, n) is None]
            if missing:
                raise ValueError(f"method 'five_factor' requires: {', '.join(missing)}")
        return self


class DuPontResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = Field(default="DuPont Analysis")
    method: DuPontMethod
    return_on_equity: float = Field(
        description="ROE as the product of the components (decimal, 0.15 = 15%)."
    )
    components: list[MetricValue] = Field(description="Factors whose product equals the ROE.")
