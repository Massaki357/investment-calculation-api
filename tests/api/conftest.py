from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="module")
def module_client() -> Iterator[TestClient]:
    """One app per test module for stateless calculation endpoints (OpenAPI generated once)."""
    settings = Settings(_env_file=None, app_env="test", log_level="WARNING")  # type: ignore[call-arg]
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def openapi(module_client: TestClient) -> dict[str, Any]:
    return module_client.get("/openapi.json").json()
