"""Schemas shared by every domain: base request, metric response and error envelope."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BaseRequest(BaseModel):
    """Base for every calculation request.

    - Unknown fields are rejected (catches typos such as `earning_per_share`).
    - NaN and Infinity are rejected: JSON cannot represent them and they poison results.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MonetaryRequest(BaseRequest):
    """Base for requests carrying monetary amounts. `currency` is informational only."""

    currency: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Optional ISO 4217 code (e.g. BRL, USD). Never changes the math.",
        examples=["BRL"],
    )


class Unit(StrEnum):
    MULTIPLE = "multiple"
    DECIMAL = "decimal"
    AMOUNT = "amount"
    INDEX = "index"
    YEARS = "years"
    NUMBER = "number"


UNIT_DESCRIPTION = (
    "multiple: ratio read as 'x' (P/E 8.45) · "
    "decimal: rate or percentage in decimal form (0.10 = 10%) · "
    "amount: monetary value in the input currency · "
    "index: indicator on its own conventional scale (RSI 0-100) · "
    "years: time in years · "
    "number: dimensionless number (beta, z-score)"
)


class MetricValue(BaseModel):
    """A named numeric value with its unit. Values are never rounded."""

    model_config = ConfigDict(allow_inf_nan=False)

    metric: str = Field(description="Name of the calculated metric.", examples=["P/E"])
    value: float = Field(description="Full-precision result (float64).", examples=[8.452380952])
    unit: Unit = Field(description=UNIT_DESCRIPTION, examples=[Unit.MULTIPLE])


class MetricResponse(MetricValue):
    """Result of a single-value calculation. Values are never rounded."""

    currency: str | None = Field(
        default=None,
        description="Echo of the request currency, when informed and applicable.",
    )


class MetricBreakdownResponse(MetricResponse):
    """Headline metric plus the intermediate values used to compute it."""

    components: list[MetricValue] = Field(
        description="Intermediate values and inputs that explain the headline value."
    )


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"


class ErrorBody(BaseModel):
    code: str = Field(
        description="Stable machine-readable error code.",
        examples=["DIVISION_BY_ZERO"],
    )
    message: str = Field(
        description="Human-readable explanation.",
        examples=["earnings_per_share cannot be zero"],
    )
    details: Any = Field(
        default=None,
        description="Optional structured context, e.g. the list of invalid fields for 422.",
    )


class ErrorResponse(BaseModel):
    error: ErrorBody


_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Invalid data for the calculation (e.g. DIVISION_BY_ZERO, INVALID_INPUT, "
    "INSUFFICIENT_DATA, CONVERGENCE_ERROR, NON_FINITE_RESULT, MALFORMED_REQUEST), or a safety "
    "limit was exceeded (LIMIT_EXCEEDED: series length, grid size, simulation cells, time limit).",
    401: "Missing or invalid X-API-Key (only when authentication is enabled).",
    404: "Endpoint or resource not found (NOT_FOUND).",
    413: "Request body larger than MAX_REQUEST_BODY_BYTES (PAYLOAD_TOO_LARGE).",
    422: "Request body failed schema validation (VALIDATION_ERROR).",
    500: "Unexpected internal error (INTERNAL_ERROR). No internal details are exposed.",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Build the `responses=` mapping that documents error envelopes in OpenAPI."""
    codes = status_codes or (400, 413, 422, 500)
    return {
        code: {"model": ErrorResponse, "description": _ERROR_DESCRIPTIONS[code]} for code in codes
    }
