"""Translate every failure into the standard error envelope, without leaking internals."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("errors")

_HTTP_CODES: dict[int, str] = {
    400: "MALFORMED_REQUEST",  # body that could not be parsed at all (e.g. absurdly nested JSON)
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
        headers=headers,
    )


def _format_field(location: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in location)


# Starlette types handlers as (Request, Exception); each one narrows to the type it is
# registered for and re-raises anything else so it reaches the catch-all 500 handler.


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = exc.errors()

    if any(error.get("type") == "json_invalid" for error in errors):
        return error_response(400, "MALFORMED_REQUEST", "Request body is not valid JSON")

    # Only field path, message and type: never echo the submitted input back.
    details = [
        {
            "field": _format_field(error.get("loc", ())),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in errors
    ]
    return error_response(422, "VALIDATION_ERROR", "Request validation failed", details)


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    status_code = exc.status_code
    code = _HTTP_CODES.get(status_code, "HTTP_ERROR")
    try:
        default_message = HTTPStatus(status_code).phrase
    except ValueError:
        default_message = "HTTP error"
    message = exc.detail if isinstance(exc.detail, str) else default_message
    return error_response(status_code, code, message, headers=exc.headers)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled exception",
        exc_info=exc,
        extra={"request_id": request_id, "method": request.method, "path": request.url.path},
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred", headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
