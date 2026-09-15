"""Valuation routes: /api/v1/valuation/*."""

from fastapi import APIRouter

from app.api.v1.routes.valuation import cost_of_capital, dcf, ddm

_GROUPS = (dcf, ddm, cost_of_capital)

router = APIRouter(prefix="/valuation")
for _group in _GROUPS:
    router.include_router(_group.router)

METRIC_ENDPOINTS = tuple(endpoint for group in _GROUPS for endpoint in group.METRIC_ENDPOINTS)
CALCULATION_ENDPOINTS = tuple(
    endpoint for group in _GROUPS for endpoint in group.CALCULATION_ENDPOINTS
)
