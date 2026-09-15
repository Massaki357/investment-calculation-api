"""Risk routes: /api/v1/risk/*."""

from fastapi import APIRouter

from app.api.v1.routes.risk import market, performance, returns, tail

_GROUPS = (returns, market, tail, performance)

router = APIRouter(prefix="/risk")
for _group in _GROUPS:
    router.include_router(_group.router)

METRIC_ENDPOINTS = tuple(endpoint for group in _GROUPS for endpoint in group.METRIC_ENDPOINTS)
CALCULATION_ENDPOINTS = tuple(
    endpoint for group in _GROUPS for endpoint in group.CALCULATION_ENDPOINTS
)
