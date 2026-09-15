"""Every valuation endpoint is documented and its examples match the live API."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.valuation import CALCULATION_ENDPOINTS, METRIC_ENDPOINTS

BASE = "/api/v1/valuation"
ALL_PATHS = sorted(e.path for e in (*METRIC_ENDPOINTS, *CALCULATION_ENDPOINTS))


def test_valuation_exposes_expected_endpoint_count(openapi: dict[str, Any]) -> None:
    documented = [p for p in openapi["paths"] if p.startswith(BASE)]
    assert sorted(documented) == [BASE + path for path in ALL_PATHS]
    assert len(ALL_PATHS) == 21


@pytest.mark.parametrize("path", ALL_PATHS)
def test_description_formula_and_errors(openapi: dict[str, Any], path: str) -> None:
    operation = openapi["paths"][BASE + path]["post"]

    assert "**Formula" in operation["description"]
    assert {"200", "400", "422", "500"} <= set(operation["responses"])


@pytest.mark.parametrize("path", ALL_PATHS)
def test_every_documented_example_matches_live_response(
    client: TestClient, openapi: dict[str, Any], path: str
) -> None:
    content = openapi["paths"][BASE + path]["post"]
    request_examples = content["requestBody"]["content"]["application/json"]["examples"]
    response_examples = content["responses"]["200"]["content"]["application/json"]["examples"]

    assert request_examples.keys() == response_examples.keys()
    for name, example in request_examples.items():
        live = client.post(BASE + path, json=example["value"])
        assert live.status_code == 200, (name, live.text)
        assert _without_nulls(live.json()) == response_examples[name]["value"]


def _without_nulls(value: Any) -> Any:
    """FastAPI serializes the OpenAPI document with exclude_none, dropping null example fields."""
    if isinstance(value, dict):
        return {key: _without_nulls(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_nulls(item) for item in value]
    return value
