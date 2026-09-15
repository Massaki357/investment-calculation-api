from fastapi import APIRouter

from app.api.metric_endpoint import MetricEndpoint, add_metric_endpoints
from app.api.v1.routes.fundamentals.common import SIGNED_RESULT_NOTE
from app.schemas.common import Unit
from app.schemas.fundamentals import debt as schemas
from app.services.fundamentals import debt as calc

router = APIRouter(tags=["Fundamentals · Debt"])

ENDPOINTS = (
    MetricEndpoint(
        path="/gross-debt",
        metric="Gross Debt",
        unit=Unit.AMOUNT,
        summary="Gross debt (Dívida Bruta)",
        formula="Gross Debt = short_term_debt + long_term_debt + lease_liabilities",
        request_model=schemas.GrossDebtRequest,
        compute=lambda r: calc.gross_debt(r.short_term_debt, r.long_term_debt, r.lease_liabilities),
        example={"short_term_debt": 200.0, "long_term_debt": 800.0, "lease_liabilities": 100.0},
        notes=("lease_liabilities defaults to 0 and is included only when informed.",),
    ),
    MetricEndpoint(
        path="/net-debt",
        metric="Net Debt",
        unit=Unit.AMOUNT,
        summary="Net debt (Dívida Líquida)",
        formula="Net Debt = gross_debt − cash_and_equivalents − short_term_investments",
        request_model=schemas.NetDebtRequest,
        compute=lambda r: calc.net_debt(
            r.gross_debt, r.cash_and_equivalents, r.short_term_investments
        ),
        example={
            "gross_debt": 1100.0,
            "cash_and_equivalents": 300.0,
            "short_term_investments": 100.0,
        },
        notes=("A negative result means a net cash position.",),
    ),
    MetricEndpoint(
        path="/net-debt-to-ebitda",
        metric="Net Debt/EBITDA",
        unit=Unit.MULTIPLE,
        summary="Net debt to EBITDA (Dívida Líquida/EBITDA)",
        formula="Net Debt/EBITDA = net_debt / ebitda",
        request_model=schemas.NetDebtToEbitdaRequest,
        compute=lambda r: calc.net_debt_to_ebitda(r.net_debt, r.ebitda),
        example={"net_debt": 700.0, "ebitda": 350.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/debt-to-equity",
        metric="Debt/Equity",
        unit=Unit.MULTIPLE,
        summary="Debt to equity (Dívida/Patrimônio)",
        formula="Debt/Equity = gross_debt / shareholders_equity",
        request_model=schemas.DebtToEquityRequest,
        compute=lambda r: calc.debt_to_equity(r.gross_debt, r.shareholders_equity),
        example={"gross_debt": 1100.0, "shareholders_equity": 2200.0},
        notes=("Uses gross debt.", SIGNED_RESULT_NOTE),
    ),
    MetricEndpoint(
        path="/debt-to-capital",
        metric="Debt/Total Capital",
        unit=Unit.DECIMAL,
        summary="Debt to total capital (Dívida/Capital Total)",
        formula="Debt/Capital = gross_debt / (gross_debt + shareholders_equity)",
        request_model=schemas.DebtToCapitalRequest,
        compute=lambda r: calc.debt_to_capital(r.gross_debt, r.shareholders_equity),
        example={"gross_debt": 1100.0, "shareholders_equity": 2200.0},
        notes=("Book values; send market values if that is the desired basis.",),
    ),
    MetricEndpoint(
        path="/interest-coverage",
        metric="Interest Coverage",
        unit=Unit.MULTIPLE,
        summary="Interest coverage (Cobertura de Juros)",
        formula="Interest Coverage = ebit / interest_expense",
        request_model=schemas.InterestCoverageRequest,
        compute=lambda r: calc.interest_coverage(r.ebit, r.interest_expense),
        example={"ebit": 300.0, "interest_expense": 60.0},
        notes=("interest_expense is a positive magnitude; 0 returns DIVISION_BY_ZERO.",),
    ),
    MetricEndpoint(
        path="/debt-to-fcf",
        metric="Debt/FCF",
        unit=Unit.MULTIPLE,
        summary="Debt to free cash flow",
        formula="Debt/FCF = gross_debt / free_cash_flow",
        request_model=schemas.DebtToFreeCashFlowRequest,
        compute=lambda r: calc.debt_to_free_cash_flow(r.gross_debt, r.free_cash_flow),
        example={"gross_debt": 1100.0, "free_cash_flow": 220.0},
        notes=("Uses gross debt.", SIGNED_RESULT_NOTE),
    ),
)

add_metric_endpoints(router, ENDPOINTS)
