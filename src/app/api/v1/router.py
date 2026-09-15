"""Aggregates every v1 domain router under /api/v1.

A future v2 lives in a sibling package (app.api.v2) and is mounted alongside, leaving v1 untouched.
"""

from fastapi import APIRouter, Depends

from app.api.v1.routes import (
    fixed_income,
    fundamentals,
    portfolio,
    risk,
    scenarios,
    statistics,
    technical,
    valuation,
)
from app.core.security import verify_api_key

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX, dependencies=[Depends(verify_api_key)])
api_router.include_router(fundamentals.router)
api_router.include_router(valuation.router)
api_router.include_router(fixed_income.router)
api_router.include_router(risk.router)
api_router.include_router(statistics.router)
api_router.include_router(portfolio.router)
api_router.include_router(technical.router)
api_router.include_router(scenarios.router)
