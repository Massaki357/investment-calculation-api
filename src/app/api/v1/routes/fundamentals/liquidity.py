from fastapi import APIRouter

from app.api.endpoint_specs import MetricEndpoint, add_metric_endpoints
from app.schemas.common import Unit
from app.schemas.fundamentals import liquidity as schemas
from app.services.fundamentals import liquidity as calc

router = APIRouter(tags=["Fundamentals · Liquidity"])

ENDPOINTS = (
    MetricEndpoint(
        path="/current-ratio",
        metric="Current Ratio",
        unit=Unit.MULTIPLE,
        summary="Current ratio (Liquidez Corrente)",
        formula="Current Ratio = current_assets / current_liabilities",
        request_model=schemas.CurrentRatioRequest,
        compute=lambda r: calc.current_ratio(r.current_assets, r.current_liabilities),
        example={"current_assets": 1500.0, "current_liabilities": 1000.0},
    ),
    MetricEndpoint(
        path="/quick-ratio",
        metric="Quick Ratio",
        unit=Unit.MULTIPLE,
        summary="Quick ratio (Liquidez Seca)",
        formula="Quick Ratio = (current_assets − inventories) / current_liabilities",
        request_model=schemas.QuickRatioRequest,
        compute=lambda r: calc.quick_ratio(r.current_assets, r.inventories, r.current_liabilities),
        example={"current_assets": 1500.0, "inventories": 500.0, "current_liabilities": 1000.0},
        notes=(
            "Only inventories are excluded (Brazilian convention).",
            "inventories > current_assets returns INVALID_INPUT.",
        ),
    ),
    MetricEndpoint(
        path="/cash-ratio",
        metric="Cash Ratio",
        unit=Unit.MULTIPLE,
        summary="Cash ratio (Liquidez Imediata)",
        formula="Cash Ratio = (cash_and_equivalents + short_term_investments) "
        "/ current_liabilities",
        request_model=schemas.CashRatioRequest,
        compute=lambda r: calc.cash_ratio(
            r.cash_and_equivalents, r.current_liabilities, r.short_term_investments
        ),
        example={
            "cash_and_equivalents": 300.0,
            "short_term_investments": 100.0,
            "current_liabilities": 1000.0,
        },
        notes=("short_term_investments defaults to 0.",),
    ),
    MetricEndpoint(
        path="/general-liquidity-ratio",
        metric="General Liquidity Ratio",
        unit=Unit.MULTIPLE,
        summary="General liquidity ratio (Liquidez Geral)",
        formula="(current_assets + long_term_receivables) / "
        "(current_liabilities + non_current_liabilities)",
        request_model=schemas.GeneralLiquidityRequest,
        compute=lambda r: calc.general_liquidity_ratio(
            r.current_assets,
            r.long_term_receivables,
            r.current_liabilities,
            r.non_current_liabilities,
        ),
        example={
            "current_assets": 1500.0,
            "long_term_receivables": 500.0,
            "current_liabilities": 1000.0,
            "non_current_liabilities": 1500.0,
        },
    ),
)

add_metric_endpoints(router, ENDPOINTS)
