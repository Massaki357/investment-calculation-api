"""Every registered calculation endpoint, in every domain, is documented and its examples are live.

New domains only need to be added to DOMAINS.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import fixed_income, fundamentals, risk, statistics, valuation

DOMAINS = {
    "/api/v1/fundamentals": fundamentals,
    "/api/v1/valuation": valuation,
    "/api/v1/fixed-income": fixed_income,
    "/api/v1/risk": risk,
    "/api/v1/statistics": statistics,
}

ENDPOINT_PATHS = sorted(
    prefix + endpoint.path
    for prefix, module in DOMAINS.items()
    for endpoint in (*module.METRIC_ENDPOINTS, *module.CALCULATION_ENDPOINTS)
)


def _without_nulls(value: Any) -> Any:
    """FastAPI serializes the OpenAPI document with exclude_none, dropping null example fields."""
    if isinstance(value, dict):
        return {key: _without_nulls(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_nulls(item) for item in value]
    return value


def test_every_registered_endpoint_is_published(openapi: dict[str, Any]) -> None:
    published = {
        path for path in openapi["paths"] if path.startswith(tuple(DOMAINS)) and path != "/health"
    }
    assert published == set(ENDPOINT_PATHS)


@pytest.mark.parametrize("path", ENDPOINT_PATHS)
def test_description_formula_and_error_responses(openapi: dict[str, Any], path: str) -> None:
    operation = openapi["paths"][path]["post"]

    assert operation["summary"]
    assert "**Formula" in operation["description"]
    assert {"200", "400", "422", "500"} <= set(operation["responses"])
    error_schema = operation["responses"]["400"]["content"]["application/json"]["schema"]
    assert error_schema == {"$ref": "#/components/schemas/ErrorResponse"}


@pytest.mark.parametrize("path", ENDPOINT_PATHS)
def test_every_documented_example_matches_live_response(
    module_client: TestClient, openapi: dict[str, Any], path: str
) -> None:
    operation = openapi["paths"][path]["post"]
    request_examples = operation["requestBody"]["content"]["application/json"]["examples"]
    response_examples = operation["responses"]["200"]["content"]["application/json"]["examples"]

    assert request_examples
    assert request_examples.keys() == response_examples.keys()
    for name, example in request_examples.items():
        live = module_client.post(path, json=example["value"])
        assert live.status_code == 200, (name, live.text)
        assert _without_nulls(live.json()) == response_examples[name]["value"]


@pytest.mark.parametrize("path", ENDPOINT_PATHS)
def test_unknown_fields_are_rejected(
    module_client: TestClient, openapi: dict[str, Any], path: str
) -> None:
    operation = openapi["paths"][path]["post"]
    example = next(
        iter(operation["requestBody"]["content"]["application/json"]["examples"].values())
    )

    response = module_client.post(path, json={**example["value"], "unexpected_field": 1})

    assert response.status_code == 422


@pytest.mark.parametrize("path", ENDPOINT_PATHS)
def test_empty_body_is_rejected(module_client: TestClient, path: str) -> None:
    response = module_client.post(path, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
