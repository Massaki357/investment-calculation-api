from pydantic import Field

from app.schemas.fundamentals.common import (
    CashAndEquivalents,
    CurrentAssets,
    CurrentLiabilities,
    FundamentalsRequest,
    ShortTermInvestments,
)


class CurrentRatioRequest(FundamentalsRequest):
    current_assets: CurrentAssets
    current_liabilities: CurrentLiabilities


class QuickRatioRequest(FundamentalsRequest):
    current_assets: CurrentAssets
    inventories: float = Field(ge=0, description="Inventories (≥ 0, ≤ current_assets).")
    current_liabilities: CurrentLiabilities


class CashRatioRequest(FundamentalsRequest):
    cash_and_equivalents: CashAndEquivalents
    short_term_investments: ShortTermInvestments = 0
    current_liabilities: CurrentLiabilities


class GeneralLiquidityRequest(FundamentalsRequest):
    current_assets: CurrentAssets
    long_term_receivables: float = Field(
        ge=0, description="Long-term receivables / realizable assets (Realizável a Longo Prazo)."
    )
    current_liabilities: CurrentLiabilities
    non_current_liabilities: float = Field(ge=0, description="Non-current liabilities (≥ 0).")
