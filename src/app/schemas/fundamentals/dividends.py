from typing import Annotated

from pydantic import Field

from app.schemas.fundamentals.common import (
    EarningsPerShare,
    FundamentalsRequest,
    NetIncome,
    SharePrice,
    SharesOutstanding,
)

DividendPerShare = Annotated[
    float, Field(ge=0, description="Dividend per share for the period (≥ 0).")
]


class DividendYieldRequest(FundamentalsRequest):
    dividend_per_share: DividendPerShare
    share_price: SharePrice


class DividendPayoutRequest(FundamentalsRequest):
    dividends_paid: float = Field(ge=0, description="Total dividends paid (≥ 0).")
    net_income: NetIncome


class DividendCoverageRequest(FundamentalsRequest):
    earnings_per_share: EarningsPerShare
    dividend_per_share: DividendPerShare


class DividendCagrRequest(FundamentalsRequest):
    beginning_dividend: float = Field(description="Dividend at the start (must be > 0).")
    ending_dividend: float = Field(description="Dividend at the end (must be > 0).")
    years: float = Field(gt=0, description="Elapsed time in years (> 0).")


class DividendPerShareRequest(FundamentalsRequest):
    total_dividends: float = Field(ge=0, description="Total dividends distributed (≥ 0).")
    shares_outstanding: SharesOutstanding


class YieldOnCostRequest(FundamentalsRequest):
    dividend_per_share: DividendPerShare
    average_cost_per_share: float = Field(
        gt=0, description="Average acquisition cost per share (> 0)."
    )
