"""Reusable, documented field types for fundamentals requests.

Cross-domain field types (tax rate, share price, shares...) live in app.schemas.fields,
which also documents where validation happens (schema -> 422, service -> 400).
"""

from typing import Annotated

from pydantic import Field

from app.schemas.common import BaseRequest, MonetaryRequest


class PeriodBalance(BaseRequest):
    """Beginning and ending balances; the calculation uses their simple average."""

    beginning: float = Field(description="Balance at the beginning of the period.")
    ending: float = Field(description="Balance at the end of the period.")


class FundamentalsRequest(MonetaryRequest):
    """Base for every fundamentals request (all accept an optional informational `currency`)."""


_AVERAGE_HINT = " Send a number, or {beginning, ending} to use the simple average of the period."

# --- Balances (number or {beginning, ending}) ---
ShareholdersEquityBalance = Annotated[
    float | PeriodBalance,
    Field(description="Total shareholders' equity (can be negative)." + _AVERAGE_HINT),
]
TotalAssetsBalance = Annotated[
    float | PeriodBalance, Field(description="Total assets." + _AVERAGE_HINT)
]
InvestedCapitalBalance = Annotated[
    float | PeriodBalance, Field(description="Invested capital." + _AVERAGE_HINT)
]

# --- Market data supplied by the caller ---
MarketCapitalization = Annotated[
    float, Field(gt=0, description="Market capitalization: price × shares outstanding (> 0).")
]
EnterpriseValue = Annotated[
    float,
    Field(description="Enterprise value: market cap + net debt (+ minorities). Can be negative."),
]

# --- Income statement ---
Revenue = Annotated[float, Field(description="Net revenue for the period.")]
GrossProfit = Annotated[float, Field(description="Gross profit: revenue − cost of goods sold.")]
Ebitda = Annotated[float, Field(description="EBITDA for the period (can be negative).")]
Ebit = Annotated[float, Field(description="EBIT / operating income for the period.")]
PretaxIncome = Annotated[float, Field(description="Earnings before taxes (EBT).")]
NetIncome = Annotated[float, Field(description="Net income for the period (can be negative).")]
EarningsPerShare = Annotated[
    float, Field(description="Earnings per share for the period (can be negative).")
]
BookValuePerShare = Annotated[float, Field(description="Book value (equity) per share.")]
InterestExpense = Annotated[
    float, Field(ge=0, description="Interest expense as a positive magnitude (≥ 0).")
]

# --- Cash flow statement ---
OperatingCashFlow = Annotated[float, Field(description="Cash flow from operations (CFO).")]
FreeCashFlow = Annotated[float, Field(description="Free cash flow (can be negative).")]
CapitalExpenditures = Annotated[
    float,
    Field(
        ge=0,
        description="Capital expenditures as a positive magnitude (≥ 0), even if the "
        "cash flow statement reports it as negative.",
    ),
]
DepreciationAmortization = Annotated[
    float, Field(ge=0, description="Depreciation and amortization, positive magnitude (≥ 0).")
]
ChangeInWorkingCapital = Annotated[
    float,
    Field(description="Change in net working capital. Positive = investment (cash outflow)."),
]

# --- Balance sheet ---
GrossDebt = Annotated[
    float, Field(ge=0, description="Gross debt: short + long-term borrowings (+ leases) (≥ 0).")
]
CashAndEquivalents = Annotated[float, Field(ge=0, description="Cash and cash equivalents (≥ 0).")]
ShortTermInvestments = Annotated[
    float,
    Field(ge=0, description="Short-term financial investments with immediate liquidity (≥ 0)."),
]
CurrentAssets = Annotated[float, Field(ge=0, description="Total current assets (≥ 0).")]
CurrentLiabilities = Annotated[float, Field(ge=0, description="Total current liabilities (≥ 0).")]

# --- Rates ---
GrowthRateDecimal = Annotated[
    float, Field(description="Growth rate in decimal form (0.15 = 15%). Can be negative.")
]
