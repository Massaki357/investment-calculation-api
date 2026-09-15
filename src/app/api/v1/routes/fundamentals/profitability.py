from typing import cast

from fastapi import APIRouter

from app.api.endpoint_specs import (
    CalculationEndpoint,
    MetricEndpoint,
    add_calculation_endpoints,
    add_metric_endpoints,
)
from app.api.v1.routes.fundamentals.common import (
    AVERAGE_BALANCE_NOTE,
    SIGNED_RESULT_NOTE,
    resolve_balance,
)
from app.schemas.common import MetricValue, Unit
from app.schemas.fundamentals import profitability as schemas
from app.schemas.fundamentals.profitability import DuPontMethod, DuPontRequest, DuPontResponse
from app.services.fundamentals import profitability as calc

router = APIRouter(tags=["Fundamentals · Profitability"])


def _roic(r: schemas.ReturnOnInvestedCapitalRequest) -> float:
    if r.invested_capital is not None:
        capital = resolve_balance(r.invested_capital)
    else:
        capital = calc.invested_capital(
            cast(float, r.total_debt),
            cast(float, r.shareholders_equity),
            cast(float, r.cash_and_equivalents),
        )
    return calc.return_on_invested_capital(r.ebit, r.tax_rate, capital)


ENDPOINTS = (
    MetricEndpoint(
        path="/roe",
        metric="ROE",
        unit=Unit.DECIMAL,
        summary="Return on equity",
        formula="ROE = net_income / shareholders_equity",
        request_model=schemas.ReturnOnEquityRequest,
        compute=lambda r: calc.return_on_equity(
            r.net_income, resolve_balance(r.shareholders_equity)
        ),
        example={"net_income": 180.0, "shareholders_equity": 1000.0},
        notes=(AVERAGE_BALANCE_NOTE, SIGNED_RESULT_NOTE),
    ),
    MetricEndpoint(
        path="/roa",
        metric="ROA",
        unit=Unit.DECIMAL,
        summary="Return on assets",
        formula="ROA = net_income / total_assets",
        request_model=schemas.ReturnOnAssetsRequest,
        compute=lambda r: calc.return_on_assets(r.net_income, resolve_balance(r.total_assets)),
        example={"net_income": 180.0, "total_assets": 2400.0},
        notes=(AVERAGE_BALANCE_NOTE,),
    ),
    MetricEndpoint(
        path="/roic",
        metric="ROIC",
        unit=Unit.DECIMAL,
        summary="Return on invested capital",
        formula="ROIC = ebit × (1 − tax_rate) / invested_capital",
        request_model=schemas.ReturnOnInvestedCapitalRequest,
        compute=_roic,
        example={"ebit": 300.0, "tax_rate": 0.34, "invested_capital": 1200.0},
        notes=(
            "NOPAT = ebit × (1 − tax_rate).",
            "Invested capital is sent directly, or computed as "
            "total_debt + shareholders_equity − cash_and_equivalents (financing approach).",
            AVERAGE_BALANCE_NOTE,
        ),
    ),
    MetricEndpoint(
        path="/roce",
        metric="ROCE",
        unit=Unit.DECIMAL,
        summary="Return on capital employed",
        formula="ROCE = ebit / (total_assets − current_liabilities)",
        request_model=schemas.ReturnOnCapitalEmployedRequest,
        compute=lambda r: calc.return_on_capital_employed(
            r.ebit, r.total_assets, r.current_liabilities
        ),
        example={"ebit": 300.0, "total_assets": 2400.0, "current_liabilities": 400.0},
        notes=("Capital employed = total_assets − current_liabilities.",),
    ),
    MetricEndpoint(
        path="/gross-margin",
        metric="Gross Margin",
        unit=Unit.DECIMAL,
        summary="Gross margin (Margem Bruta)",
        formula="Gross Margin = gross_profit / revenue",
        request_model=schemas.GrossMarginRequest,
        compute=lambda r: calc.margin(r.gross_profit, r.revenue),
        example={"gross_profit": 400.0, "revenue": 1000.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ebitda-margin",
        metric="EBITDA Margin",
        unit=Unit.DECIMAL,
        summary="EBITDA margin (Margem EBITDA)",
        formula="EBITDA Margin = ebitda / revenue",
        request_model=schemas.EbitdaMarginRequest,
        compute=lambda r: calc.margin(r.ebitda, r.revenue),
        example={"ebitda": 250.0, "revenue": 1000.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ebit-margin",
        metric="EBIT Margin",
        unit=Unit.DECIMAL,
        summary="EBIT margin (Margem EBIT)",
        formula="EBIT Margin = ebit / revenue",
        request_model=schemas.EbitMarginRequest,
        compute=lambda r: calc.margin(r.ebit, r.revenue),
        example={"ebit": 180.0, "revenue": 1000.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/net-margin",
        metric="Net Margin",
        unit=Unit.DECIMAL,
        summary="Net margin (Margem Líquida)",
        formula="Net Margin = net_income / revenue",
        request_model=schemas.NetMarginRequest,
        compute=lambda r: calc.margin(r.net_income, r.revenue),
        example={"net_income": 120.0, "revenue": 1000.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/fcf-margin",
        metric="FCF Margin",
        unit=Unit.DECIMAL,
        summary="Free cash flow margin (Margem FCF)",
        formula="FCF Margin = free_cash_flow / revenue",
        request_model=schemas.FreeCashFlowMarginRequest,
        compute=lambda r: calc.margin(r.free_cash_flow, r.revenue),
        example={"free_cash_flow": 90.0, "revenue": 1000.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/asset-turnover",
        metric="Asset Turnover",
        unit=Unit.MULTIPLE,
        summary="Asset turnover (Giro do Ativo)",
        formula="Asset Turnover = revenue / total_assets",
        request_model=schemas.AssetTurnoverRequest,
        compute=lambda r: calc.asset_turnover(r.revenue, resolve_balance(r.total_assets)),
        example={"revenue": 1000.0, "total_assets": 2000.0},
        notes=(AVERAGE_BALANCE_NOTE,),
    ),
)

add_metric_endpoints(router, ENDPOINTS)


def _dupont(payload: DuPontRequest) -> DuPontResponse:
    assets = resolve_balance(payload.total_assets)
    equity = resolve_balance(payload.shareholders_equity)

    if payload.method is DuPontMethod.FIVE_FACTOR:
        five = calc.dupont_five_factor(
            payload.net_income,
            cast(float, payload.pretax_income),
            cast(float, payload.ebit),
            payload.revenue,
            assets,
            equity,
        )
        roe = five.return_on_equity
        components = [
            MetricValue(metric="Tax Burden", value=five.tax_burden, unit=Unit.DECIMAL),
            MetricValue(metric="Interest Burden", value=five.interest_burden, unit=Unit.DECIMAL),
            MetricValue(metric="Operating Margin", value=five.operating_margin, unit=Unit.DECIMAL),
            MetricValue(metric="Asset Turnover", value=five.asset_turnover, unit=Unit.MULTIPLE),
            MetricValue(
                metric="Equity Multiplier", value=five.equity_multiplier, unit=Unit.MULTIPLE
            ),
        ]
    else:
        three = calc.dupont_three_factor(payload.net_income, payload.revenue, assets, equity)
        roe = three.return_on_equity
        components = [
            MetricValue(
                metric="Net Profit Margin", value=three.net_profit_margin, unit=Unit.DECIMAL
            ),
            MetricValue(metric="Asset Turnover", value=three.asset_turnover, unit=Unit.MULTIPLE),
            MetricValue(
                metric="Equity Multiplier", value=three.equity_multiplier, unit=Unit.MULTIPLE
            ),
        ]

    return DuPontResponse(method=payload.method, return_on_equity=roe, components=components)


STRUCTURED_ENDPOINTS = (
    CalculationEndpoint(
        path="/dupont",
        title="DuPont Analysis",
        summary="DuPont decomposition of return on equity",
        formulas=(
            "three_factor (default): ROE = (net_income / revenue) × (revenue / total_assets) "
            "× (total_assets / shareholders_equity)",
            "five_factor: ROE = (net_income / pretax_income) × (pretax_income / ebit) "
            "× (ebit / revenue) × (revenue / total_assets) × (total_assets / shareholders_equity)",
        ),
        request_model=DuPontRequest,
        response_model=DuPontResponse,
        compute=_dupont,
        examples={
            "three_factor": {
                "method": "three_factor",
                "net_income": 120.0,
                "revenue": 1000.0,
                "total_assets": 2000.0,
                "shareholders_equity": 800.0,
            },
            "five_factor": {
                "method": "five_factor",
                "net_income": 120.0,
                "pretax_income": 160.0,
                "ebit": 200.0,
                "revenue": 1000.0,
                "total_assets": 2000.0,
                "shareholders_equity": 800.0,
            },
        },
        notes=(
            "Margins, burdens and ROE are decimals; turnover and equity multiplier are multiples.",
            AVERAGE_BALANCE_NOTE,
            "ROE is the product of the components, so it equals net_income / shareholders_equity "
            "when the same balances are used.",
        ),
    ),
)

add_calculation_endpoints(router, STRUCTURED_ENDPOINTS)
