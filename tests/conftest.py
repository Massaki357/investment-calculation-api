from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import DivisionByZeroError
from app.core.security import verify_api_key
from app.main import create_app
from app.schemas.common import BaseRequest, MetricResponse, Unit, error_responses
from app.utils.math import safe_divide

SettingsFactory = Callable[..., Settings]
ClientFactory = Callable[..., TestClient]


class RatioRequest(BaseRequest):
    numerator: float
    denominator: float


def build_probe_router() -> APIRouter:
    """Routes that exist only in tests, to exercise the error pipeline end to end."""
    router = APIRouter(prefix="/_test", dependencies=[Depends(verify_api_key)])

    @router.post("/ratio", response_model=MetricResponse, responses=error_responses())
    def ratio(payload: RatioRequest) -> MetricResponse:
        value = safe_divide(payload.numerator, payload.denominator, denominator_name="denominator")
        return MetricResponse(metric="ratio", value=value, unit=Unit.MULTIPLE)

    @router.get("/domain-error")
    def domain_error() -> None:
        raise DivisionByZeroError("earnings_per_share cannot be zero")

    @router.get("/crash")
    def crash() -> None:
        raise RuntimeError("secret internal detail: /srv/app/db.py line 42")

    return router


@pytest.fixture
def make_settings() -> SettingsFactory:
    def factory(**overrides: Any) -> Settings:
        values: dict[str, Any] = {"app_env": "test", "log_level": "WARNING"}
        values.update(overrides)
        return Settings(_env_file=None, **values)  # type: ignore[call-arg]

    return factory


@pytest.fixture
def make_app(make_settings: SettingsFactory) -> Callable[..., FastAPI]:
    def factory(**overrides: Any) -> FastAPI:
        app = create_app(make_settings(**overrides))
        app.include_router(build_probe_router())
        return app

    return factory


@pytest.fixture
def make_client(make_app: Callable[..., FastAPI]) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def factory(*, raise_server_exceptions: bool = True, **overrides: Any) -> TestClient:
        client = TestClient(make_app(**overrides), raise_server_exceptions=raise_server_exceptions)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()
