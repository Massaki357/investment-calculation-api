from pydantic import Field

from app.schemas.fundamentals.common import (
    CashAndEquivalents,
    Ebit,
    Ebitda,
    FreeCashFlow,
    FundamentalsRequest,
    GrossDebt,
    InterestExpense,
    ShortTermInvestments,
)


class GrossDebtRequest(FundamentalsRequest):
    short_term_debt: float = Field(ge=0, description="Short-term borrowings (≥ 0).")
    long_term_debt: float = Field(ge=0, description="Long-term borrowings (≥ 0).")
    lease_liabilities: float = Field(
        default=0, ge=0, description="Lease liabilities; included only if informed (≥ 0)."
    )


class NetDebtRequest(FundamentalsRequest):
    gross_debt: GrossDebt
    cash_and_equivalents: CashAndEquivalents
    short_term_investments: ShortTermInvestments = 0


class NetDebtToEbitdaRequest(FundamentalsRequest):
    net_debt: float = Field(description="Net debt; negative means net cash.")
    ebitda: Ebitda


class DebtToEquityRequest(FundamentalsRequest):
    gross_debt: GrossDebt
    shareholders_equity: float = Field(description="Shareholders' equity (can be negative).")


class DebtToCapitalRequest(FundamentalsRequest):
    gross_debt: GrossDebt
    shareholders_equity: float = Field(description="Shareholders' equity (can be negative).")


class InterestCoverageRequest(FundamentalsRequest):
    ebit: Ebit
    interest_expense: InterestExpense


class DebtToFreeCashFlowRequest(FundamentalsRequest):
    gross_debt: GrossDebt
    free_cash_flow: FreeCashFlow
