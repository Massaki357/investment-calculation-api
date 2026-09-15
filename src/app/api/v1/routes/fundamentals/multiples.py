from typing import cast

from fastapi import APIRouter

from app.api.metric_endpoint import MetricEndpoint, add_metric_endpoints
from app.api.v1.routes.fundamentals.common import SIGNED_RESULT_NOTE
from app.schemas.common import Unit
from app.schemas.fundamentals import multiples as schemas
from app.schemas.fundamentals.multiples import EarningsYieldMethod
from app.services.fundamentals import multiples as calc

router = APIRouter(tags=["Fundamentals · Valuation multiples"])


def _earnings_yield(r: schemas.EarningsYieldRequest) -> float:
    # The request validator guarantees the fields required by the chosen method are present.
    if r.method is EarningsYieldMethod.EBIT_TO_ENTERPRISE_VALUE:
        return calc.operating_earnings_yield(cast(float, r.ebit), cast(float, r.enterprise_value))
    return calc.earnings_yield(cast(float, r.earnings_per_share), cast(float, r.share_price))


ENDPOINTS = (
    MetricEndpoint(
        path="/pe-ratio",
        metric="P/E",
        unit=Unit.MULTIPLE,
        summary="Price to earnings (P/L)",
        formula="P/E = share_price / earnings_per_share",
        request_model=schemas.PriceToEarningsRequest,
        compute=lambda r: calc.price_to_earnings(r.share_price, r.earnings_per_share),
        example={"share_price": 35.50, "earnings_per_share": 4.20},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/pb-ratio",
        metric="P/B",
        unit=Unit.MULTIPLE,
        summary="Price to book value (P/VP)",
        formula="P/B = share_price / book_value_per_share",
        request_model=schemas.PriceToBookRequest,
        compute=lambda r: calc.price_to_book(r.share_price, r.book_value_per_share),
        example={"share_price": 20.0, "book_value_per_share": 16.0},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ps-ratio",
        metric="P/S",
        unit=Unit.MULTIPLE,
        summary="Price to sales (P/Receita)",
        formula="P/S = market_capitalization / revenue",
        request_model=schemas.PriceToSalesRequest,
        compute=lambda r: calc.price_to_sales(r.market_capitalization, r.revenue),
        example={"market_capitalization": 5_000_000_000, "revenue": 2_000_000_000},
        notes=("Equivalent to price / revenue per share.", SIGNED_RESULT_NOTE),
    ),
    MetricEndpoint(
        path="/ev-to-ebitda",
        metric="EV/EBITDA",
        unit=Unit.MULTIPLE,
        summary="Enterprise value to EBITDA",
        formula="EV/EBITDA = enterprise_value / ebitda",
        request_model=schemas.EvToEbitdaRequest,
        compute=lambda r: calc.ev_to_ebitda(r.enterprise_value, r.ebitda),
        example={"enterprise_value": 12_000_000_000, "ebitda": 1_500_000_000},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ev-to-ebit",
        metric="EV/EBIT",
        unit=Unit.MULTIPLE,
        summary="Enterprise value to EBIT",
        formula="EV/EBIT = enterprise_value / ebit",
        request_model=schemas.EvToEbitRequest,
        compute=lambda r: calc.ev_to_ebit(r.enterprise_value, r.ebit),
        example={"enterprise_value": 12_000_000_000, "ebit": 1_000_000_000},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ev-to-revenue",
        metric="EV/Revenue",
        unit=Unit.MULTIPLE,
        summary="Enterprise value to revenue (EV/Receita)",
        formula="EV/Revenue = enterprise_value / revenue",
        request_model=schemas.EvToRevenueRequest,
        compute=lambda r: calc.ev_to_revenue(r.enterprise_value, r.revenue),
        example={"enterprise_value": 12_000_000_000, "revenue": 4_000_000_000},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/ev-to-fcf",
        metric="EV/FCF",
        unit=Unit.MULTIPLE,
        summary="Enterprise value to free cash flow",
        formula="EV/FCF = enterprise_value / free_cash_flow",
        request_model=schemas.EvToFreeCashFlowRequest,
        compute=lambda r: calc.ev_to_free_cash_flow(r.enterprise_value, r.free_cash_flow),
        example={"enterprise_value": 12_000_000_000, "free_cash_flow": 800_000_000},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/earnings-yield",
        metric="Earnings Yield",
        unit=Unit.DECIMAL,
        summary="Earnings yield",
        formula="earnings_to_price: EPS / share_price · ebit_to_enterprise_value: EBIT / EV",
        request_model=schemas.EarningsYieldRequest,
        compute=_earnings_yield,
        example={"earnings_per_share": 4.20, "share_price": 35.50},
        notes=(
            "Default method is earnings_to_price (inverse of P/E).",
            "ebit_to_enterprise_value is Greenblatt's operating earnings yield.",
        ),
    ),
    MetricEndpoint(
        path="/fcf-yield",
        metric="FCF Yield",
        unit=Unit.DECIMAL,
        summary="Free cash flow yield",
        formula="FCF Yield = free_cash_flow / market_capitalization",
        request_model=schemas.FreeCashFlowYieldRequest,
        compute=lambda r: calc.free_cash_flow_yield(r.free_cash_flow, r.market_capitalization),
        example={"free_cash_flow": 400_000_000, "market_capitalization": 5_000_000_000},
        notes=("Equity perspective: FCF relative to market capitalization.",),
    ),
    MetricEndpoint(
        path="/ebitda-yield",
        metric="EBITDA Yield",
        unit=Unit.DECIMAL,
        summary="EBITDA yield",
        formula="EBITDA Yield = ebitda / enterprise_value",
        request_model=schemas.EbitdaYieldRequest,
        compute=lambda r: calc.ebitda_yield(r.ebitda, r.enterprise_value),
        example={"ebitda": 1_500_000_000, "enterprise_value": 12_000_000_000},
        notes=(SIGNED_RESULT_NOTE,),
    ),
    MetricEndpoint(
        path="/peg-ratio",
        metric="PEG",
        unit=Unit.MULTIPLE,
        summary="Price/earnings to growth",
        formula="PEG = pe_ratio / (earnings_growth_rate × 100)",
        request_model=schemas.PegRatioRequest,
        compute=lambda r: calc.peg_ratio(r.pe_ratio, r.earnings_growth_rate),
        example={"pe_ratio": 15.0, "earnings_growth_rate": 0.10},
        notes=(
            "earnings_growth_rate is sent in decimal (0.10) and converted to percentage "
            "points (10), following the conventional PEG definition.",
            SIGNED_RESULT_NOTE,
        ),
    ),
)

add_metric_endpoints(router, ENDPOINTS)
