"""Fundamental analysis routes: /api/v1/fundamentals/*."""

from fastapi import APIRouter

from app.api.v1.routes.fundamentals import (
    cash_flow,
    debt,
    dividends,
    growth,
    liquidity,
    multiples,
    profitability,
)

_GROUPS = (multiples, profitability, growth, debt, liquidity, cash_flow, dividends)

router = APIRouter(prefix="/fundamentals")
for _group in _GROUPS:
    router.include_router(_group.router)

METRIC_ENDPOINTS = tuple(endpoint for group in _GROUPS for endpoint in group.ENDPOINTS)
CALCULATION_ENDPOINTS = profitability.CALCULATION_ENDPOINTS
