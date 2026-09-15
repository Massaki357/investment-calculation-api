from fastapi import APIRouter

from app.api.metric_endpoint import MetricEndpoint, add_metric_endpoints
from app.schemas.common import Unit
from app.schemas.fundamentals import dividends as schemas
from app.services.fundamentals import dividends as calc

router = APIRouter(tags=["Fundamentals · Dividends"])

ENDPOINTS = (
    MetricEndpoint(
        path="/dividend-yield",
        metric="Dividend Yield",
        unit=Unit.DECIMAL,
        summary="Dividend yield",
        formula="Dividend Yield = dividend_per_share / share_price",
        request_model=schemas.DividendYieldRequest,
        compute=lambda r: calc.dividend_yield(r.dividend_per_share, r.share_price),
        example={"dividend_per_share": 2.10, "share_price": 35.0},
        notes=("Use trailing or forward dividends consistently with the analysis.",),
    ),
    MetricEndpoint(
        path="/dividend-payout",
        metric="Dividend Payout",
        unit=Unit.DECIMAL,
        summary="Dividend payout ratio",
        formula="Payout = dividends_paid / net_income",
        request_model=schemas.DividendPayoutRequest,
        compute=lambda r: calc.dividend_payout_ratio(r.dividends_paid, r.net_income),
        example={"dividends_paid": 60.0, "net_income": 120.0},
        notes=("Negative net income returns a negative payout without interpretation.",),
    ),
    MetricEndpoint(
        path="/dividend-coverage",
        metric="Dividend Coverage",
        unit=Unit.MULTIPLE,
        summary="Dividend coverage",
        formula="Coverage = earnings_per_share / dividend_per_share",
        request_model=schemas.DividendCoverageRequest,
        compute=lambda r: calc.dividend_coverage(r.earnings_per_share, r.dividend_per_share),
        example={"earnings_per_share": 4.20, "dividend_per_share": 2.10},
        notes=("dividend_per_share = 0 returns DIVISION_BY_ZERO.",),
    ),
    MetricEndpoint(
        path="/dividend-cagr",
        metric="Dividend CAGR",
        unit=Unit.DECIMAL,
        summary="Dividend compound annual growth rate",
        formula="Dividend CAGR = (ending_dividend / beginning_dividend) ^ (1 / years) − 1",
        request_model=schemas.DividendCagrRequest,
        compute=lambda r: calc.dividend_cagr(r.beginning_dividend, r.ending_dividend, r.years),
        example={"beginning_dividend": 1.00, "ending_dividend": 1.61051, "years": 5},
        notes=("Both dividends must be > 0 (INVALID_INPUT otherwise).",),
    ),
    MetricEndpoint(
        path="/dividend-per-share",
        metric="Dividend per Share",
        unit=Unit.AMOUNT,
        summary="Dividend per share",
        formula="DPS = total_dividends / shares_outstanding",
        request_model=schemas.DividendPerShareRequest,
        compute=lambda r: calc.dividend_per_share(r.total_dividends, r.shares_outstanding),
        example={"total_dividends": 60_000_000, "shares_outstanding": 50_000_000},
    ),
    MetricEndpoint(
        path="/yield-on-cost",
        metric="Yield on Cost",
        unit=Unit.DECIMAL,
        summary="Yield on cost",
        formula="Yield on Cost = dividend_per_share / average_cost_per_share",
        request_model=schemas.YieldOnCostRequest,
        compute=lambda r: calc.yield_on_cost(r.dividend_per_share, r.average_cost_per_share),
        example={"dividend_per_share": 2.10, "average_cost_per_share": 15.0},
    ),
)

add_metric_endpoints(router, ENDPOINTS)
