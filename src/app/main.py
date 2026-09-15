"""Application factory and ASGI entrypoint (`uvicorn app.main:app`)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.security import API_KEY_HEADER

API_DESCRIPTION = """
Stateless, deterministic calculation service. **Receives data → calculates → returns results.**

It does not fetch market data, does not use AI and does not issue buy/sell recommendations.

## Conventions

- **Rates are decimals**: `0.10` = 10%, `0.025` = 2.5%. Never send `10` meaning 10%.
  Technical oscillators (RSI, Stochastic, Williams %R, MFI, CCI) keep their
  conventional scale and are flagged with `unit: "index"`.
- **Currency agnostic**: amounts are plain numbers.
  `currency` is optional and never changes the math.
- **No rounding**: results are returned in full float64 precision.
- **Units**: `multiple`, `decimal`, `amount`, `index`, `years`, `number`.

## Errors

Every error uses the same envelope:

```json
{
  "error": {
    "code": "DIVISION_BY_ZERO",
    "message": "earnings_per_share cannot be zero",
    "details": null
  }
}
```

| HTTP | Meaning |
|---|---|
| 400 | Invalid data for the calculation |
| 401 | Missing/invalid `X-API-Key` (only when authentication is enabled) |
| 404 | Endpoint or resource not found |
| 422 | Schema validation error (`details` lists the invalid fields) |
| 500 | Internal error (no internal details exposed) |
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=API_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings

    # Middleware added last runs first: request context wraps CORS so every request is logged.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", API_KEY_HEADER, REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
        )
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(api_router)

    return app


app = create_app()
