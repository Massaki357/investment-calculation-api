"""Fixed income routes: /api/v1/fixed-income/*."""

from fastapi import APIRouter

from app.api.v1.routes.fixed_income import bonds, curve, interest

_GROUPS = (interest, bonds, curve)

router = APIRouter(prefix="/fixed-income")
for _group in _GROUPS:
    router.include_router(_group.router)

METRIC_ENDPOINTS = tuple(endpoint for group in _GROUPS for endpoint in group.METRIC_ENDPOINTS)
CALCULATION_ENDPOINTS = tuple(
    endpoint for group in _GROUPS for endpoint in group.CALCULATION_ENDPOINTS
)
