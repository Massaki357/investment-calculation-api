"""Optional API key authentication.

Disabled unless the API_KEY environment variable is set. When enabled, requests to
versioned routes must send the key in the X-API-Key header.
"""

import secrets

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError

API_KEY_HEADER = "X-API-Key"

_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="Required only when the server is configured with API_KEY.",
)


def verify_api_key(
    request: Request,
    provided_key: str | None = Security(_api_key_header),
) -> None:
    settings: Settings = request.app.state.settings
    if settings.api_key is None:
        return

    expected = settings.api_key.get_secret_value()
    if provided_key is None or not secrets.compare_digest(
        provided_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise UnauthorizedError("Missing or invalid API key")
