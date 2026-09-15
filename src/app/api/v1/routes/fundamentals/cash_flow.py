from fastapi import APIRouter

from app.api.metric_endpoint import MetricEndpoint, add_metric_endpoints
from app.api.v1.routes.fundamentals.common import SIGNED_RESULT_NOTE
from app.schemas.common import Unit
from app.schemas.fundamentals import cash_flow as schemas
from app.services.fundamentals import cash_flow as calc

router = APIRouter(tags=["Fundamentals · Cash flow"])

CAPEX_NOTE = "capital_expenditures is a positive magnitude."
NWC_NOTE = "change_in_working_capital > 0 means cash invested in working capital."

ENDPOINTS = (
    MetricEndpoint(
        path="/free-cash-flow",
        metric="Free Cash Flow",
        unit=Unit.AMOUNT,
        summary="Free cash flow",
        formula="FCF = operating_cash_flow − capital_expenditures",
        request_model=schemas.FreeCashFlowRequest,
        compute=lambda r: calc.free_cash_flow(r.operating_cash_flow, r.capital_expenditures),
        example={"operating_cash_flow": 500.0, "capital_expenditures": 200.0},
        notes=(CAPEX_NOTE,),
    ),
    MetricEndpoint(
        path="/fcff",
        metric="FCFF",
        unit=Unit.AMOUNT,
        summary="Free cash flow to the firm",
        formula="FCFF = ebit × (1 − tax_rate) + D&A − capex − ΔNWC",
        request_model=schemas.FcffRequest,
        compute=lambda r: calc.free_cash_flow_to_firm(
            r.ebit,
            r.tax_rate,
            r.depreciation_amortization,
            r.capital_expenditures,
            r.change_in_working_capital,
        ),
        example={
            "ebit": 300.0,
            "tax_rate": 0.34,
            "depreciation_amortization": 50.0,
            "capital_expenditures": 150.0,
            "change_in_working_capital": 20.0,
        },
        notes=(CAPEX_NOTE, NWC_NOTE),
    ),
    MetricEndpoint(
        path="/fcfe",
        metric="FCFE",
        unit=Unit.AMOUNT,
        summary="Free cash flow to equity",
        formula="FCFE = FCFF − interest_expense × (1 − tax_rate) + net_borrowing",
        request_model=schemas.FcfeRequest,
        compute=lambda r: calc.free_cash_flow_to_equity(
            r.free_cash_flow_to_firm, r.interest_expense, r.tax_rate, r.net_borrowing
        ),
        example={
            "free_cash_flow_to_firm": 78.0,
            "interest_expense": 40.0,
            "tax_rate": 0.34,
            "net_borrowing": 30.0,
        },
        notes=("Derived from FCFF: after-tax interest is removed and net borrowing added.",),
    ),
    MetricEndpoint(
        path="/fcf-conversion",
        metric="FCF Conversion",
        unit=Unit.DECIMAL,
        summary="Free cash flow conversion",
        formula="FCF Conversion = free_cash_flow / net_income",
        request_model=schemas.FcfConversionRequest,
        compute=lambda r: calc.fcf_conversion(r.free_cash_flow, r.net_income),
        example={"free_cash_flow": 90.0, "net_income": 120.0},
        notes=("Relative to net income (1.00 = 100%).", SIGNED_RESULT_NOTE),
    ),
    MetricEndpoint(
        path="/cash-conversion-ratio",
        metric="Cash Conversion Ratio",
        unit=Unit.DECIMAL,
        summary="Cash conversion ratio",
        formula="Cash Conversion = operating_cash_flow / net_income",
        request_model=schemas.CashConversionRequest,
        compute=lambda r: calc.cash_conversion_ratio(r.operating_cash_flow, r.net_income),
        example={"operating_cash_flow": 150.0, "net_income": 120.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/cfo-margin",
        metric="CFO Margin",
        unit=Unit.DECIMAL,
        summary="Operating cash flow margin",
        formula="CFO Margin = operating_cash_flow / revenue",
        request_model=schemas.CfoMarginRequest,
        compute=lambda r: calc.cfo_margin(r.operating_cash_flow, r.revenue),
        example={"operating_cash_flow": 150.0, "revenue": 1000.0},
    ),
    MetricEndpoint(
        path="/capex-to-revenue",
        metric="Capex/Revenue",
        unit=Unit.DECIMAL,
        summary="Capex to revenue (Capex/Receita)",
        formula="Capex/Revenue = capital_expenditures / revenue",
        request_model=schemas.CapexToRevenueRequest,
        compute=lambda r: calc.capex_to_revenue(r.capital_expenditures, r.revenue),
        example={"capital_expenditures": 60.0, "revenue": 1000.0},
        notes=(CAPEX_NOTE,),
    ),
    MetricEndpoint(
        path="/capex-to-depreciation",
        metric="Capex/Depreciation",
        unit=Unit.MULTIPLE,
        summary="Capex to depreciation (Capex/Depreciação)",
        formula="Capex/Depreciation = capital_expenditures / depreciation_amortization",
        request_model=schemas.CapexToDepreciationRequest,
        compute=lambda r: calc.capex_to_depreciation(
            r.capital_expenditures, r.depreciation_amortization
        ),
        example={"capital_expenditures": 60.0, "depreciation_amortization": 40.0},
        notes=(CAPEX_NOTE,),
    ),
    MetricEndpoint(
        path="/cash-flow-per-share",
        metric="Cash Flow per Share",
        unit=Unit.AMOUNT,
        summary="Operating cash flow per share",
        formula="Cash Flow per Share = operating_cash_flow / shares_outstanding",
        request_model=schemas.CashFlowPerShareRequest,
        compute=lambda r: calc.cash_flow_per_share(r.operating_cash_flow, r.shares_outstanding),
        example={"operating_cash_flow": 150.0, "shares_outstanding": 50.0},
    ),
    MetricEndpoint(
        path="/owner-earnings",
        metric="Owner Earnings",
        unit=Unit.AMOUNT,
        summary="Owner earnings (Buffett)",
        formula="Owner Earnings = net_income + D&A − maintenance_capex − ΔNWC",
        request_model=schemas.OwnerEarningsRequest,
        compute=lambda r: calc.owner_earnings(
            r.net_income,
            r.depreciation_amortization,
            r.maintenance_capital_expenditures,
            r.change_in_working_capital,
        ),
        example={
            "net_income": 120.0,
            "depreciation_amortization": 40.0,
            "maintenance_capital_expenditures": 30.0,
            "change_in_working_capital": 10.0,
        },
        notes=("Maintenance capex must be estimated by the caller.", NWC_NOTE),
    ),
)

add_metric_endpoints(router, ENDPOINTS)
