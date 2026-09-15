"""Aggregates every v1 domain router under /api/v1.

A future v2 lives in a sibling package (app.api.v2) and is mounted alongside, leaving v1 untouched.
"""

from fastapi import APIRouter, Depends

from app.api.v1.routes import fundamentals
from app.core.security import verify_api_key

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX, dependencies=[Depends(verify_api_key)])
api_router.include_router(fundamentals.router)
