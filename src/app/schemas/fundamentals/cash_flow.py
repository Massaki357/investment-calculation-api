from pydantic import Field

from app.schemas.fundamentals.common import (
    CapitalExpenditures,
    ChangeInWorkingCapital,
    DepreciationAmortization,
    Ebit,
    FreeCashFlow,
    FundamentalsRequest,
    InterestExpense,
    NetIncome,
    OperatingCashFlow,
    Revenue,
    SharesOutstanding,
    TaxRate,
)


class FreeCashFlowRequest(FundamentalsRequest):
    operating_cash_flow: OperatingCashFlow
    capital_expenditures: CapitalExpenditures


class FcffRequest(FundamentalsRequest):
    ebit: Ebit
    tax_rate: TaxRate
    depreciation_amortization: DepreciationAmortization
    capital_expenditures: CapitalExpenditures
    change_in_working_capital: ChangeInWorkingCapital


class FcfeRequest(FundamentalsRequest):
    free_cash_flow_to_firm: float = Field(description="FCFF for the period.")
    interest_expense: InterestExpense
    tax_rate: TaxRate
    net_borrowing: float = Field(
        description="New debt issued minus debt repaid. Negative = net repayment."
    )


class FcfConversionRequest(FundamentalsRequest):
    free_cash_flow: FreeCashFlow
    net_income: NetIncome


class CashConversionRequest(FundamentalsRequest):
    operating_cash_flow: OperatingCashFlow
    net_income: NetIncome


class CfoMarginRequest(FundamentalsRequest):
    operating_cash_flow: OperatingCashFlow
    revenue: Revenue


class CapexToRevenueRequest(FundamentalsRequest):
    capital_expenditures: CapitalExpenditures
    revenue: Revenue


class CapexToDepreciationRequest(FundamentalsRequest):
    capital_expenditures: CapitalExpenditures
    depreciation_amortization: DepreciationAmortization


class CashFlowPerShareRequest(FundamentalsRequest):
    operating_cash_flow: OperatingCashFlow
    shares_outstanding: SharesOutstanding


class OwnerEarningsRequest(FundamentalsRequest):
    net_income: NetIncome
    depreciation_amortization: DepreciationAmortization
    maintenance_capital_expenditures: float = Field(
        ge=0,
        description="Capex required to maintain current operations, positive magnitude (≥ 0).",
    )
    change_in_working_capital: ChangeInWorkingCapital
