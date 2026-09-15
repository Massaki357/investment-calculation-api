"""Normal / edge / invalid cases for every single-value fixed income endpoint."""

import math
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.fixed_income import METRIC_ENDPOINTS

BASE = "/api/v1/fixed-income"
V422 = (422, "VALIDATION_ERROR")
INVALID = (400, "INVALID_INPUT")
DIV0 = (400, "DIVISION_BY_ZERO")

SEMI = {"face_value": 1000, "coupon_rate": 0.06, "years_to_maturity": 5, "coupon_frequency": 2}
ANNUAL_10 = {"face_value": 1000, "coupon_rate": 0.10, "years_to_maturity": 3, "coupon_frequency": 1}
MACAULAY_10 = (1 * 100 / 1.1 + 2 * 100 / 1.1**2 + 3 * 1100 / 1.1**3) / 1000
CONVEXITY_10 = (100 * 2 / 1.1**3 + 100 * 6 / 1.1**4 + 1100 * 12 / 1.1**5) / 1000


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


CASES: dict[str, Case] = {
    "/future-value": Case(
        (
            {"present_value": 1000, "rate": 0.12, "years": 1, "compounding_frequency": 12},
            1000 * 1.01**12,
        ),
        (
            {"present_value": 1000, "rate": 0.12, "years": 2, "compounding": "simple"},
            1240.0,
        ),
        bad({"present_value": 1000, "rate": 0.12, "years": -1}, V422),
    ),
    "/present-value": Case(
        (
            {
                "future_value": 1000 * math.exp(0.12),
                "rate": 0.12,
                "years": 1,
                "compounding": "continuous",
            },
            1000.0,
        ),
        ({"future_value": 1000, "rate": 0.12, "years": 0}, 1000.0),
        bad({"future_value": 1000, "rate": -1, "years": 2, "compounding": "simple"}, INVALID),
    ),
    "/nominal-rate": Case(
        ({"effective_rate": 1.01**12 - 1, "compounding_frequency": 12}, 0.12),
        ({"effective_rate": 0.12, "compounding_frequency": 1}, 0.12),
        bad({"effective_rate": 0.12, "compounding_frequency": 0}, V422),
    ),
    "/effective-rate": Case(
        ({"nominal_rate": 0.12, "compounding_frequency": 12}, 1.01**12 - 1),
        ({"nominal_rate": 0.12, "compounding": "continuous"}, math.exp(0.12) - 1),
        bad({"nominal_rate": 0.12, "compounding": "continuous", "compounding_frequency": 12}, V422),
    ),
    "/real-rate": Case(
        ({"nominal_rate": 0.10, "inflation_rate": 0.04}, 1.10 / 1.04 - 1),
        ({"nominal_rate": 0.10, "inflation_rate": 0.04, "method": "approximate"}, 0.06),
        bad({"nominal_rate": 0.10, "inflation_rate": -1}, V422),
    ),
    "/rate-conversion": Case(
        (
            {"rate": 0.1365, "from_period": "year", "to_period": "business_day"},
            1.1365 ** (1 / 252) - 1,
        ),
        (
            {"rate": 0.10, "from_period": "year", "to_period": "day", "days_per_year": 360},
            1.10 ** (1 / 360) - 1,
        ),
        bad({"rate": 0.10, "from_period": "year", "to_period": "day", "days_per_year": 364}, V422),
    ),
    "/current-yield": Case(
        ({"face_value": 1000, "coupon_rate": 0.06, "price": 918.89}, 60 / 918.89),
        ({"face_value": 1000, "coupon_rate": 0.0, "price": 750}, 0.0),
        bad({"face_value": 1000, "coupon_rate": 0.06, "price": 0}, V422),
    ),
    "/macaulay-duration": Case(
        ({**ANNUAL_10, "yield_to_maturity": 0.10}, MACAULAY_10),
        ({**ANNUAL_10, "coupon_rate": 0, "yield_to_maturity": 0.07}, 3.0),
        bad({**ANNUAL_10, "years_to_maturity": 2.5, "yield_to_maturity": 0.10}, INVALID),
    ),
    "/modified-duration": Case(
        ({**ANNUAL_10, "yield_to_maturity": 0.10}, MACAULAY_10 / 1.1),
        ({**ANNUAL_10, "coupon_rate": 0, "yield_to_maturity": 0}, 3.0),
        bad({**ANNUAL_10, "coupon_frequency": 13, "yield_to_maturity": 0.10}, V422),
    ),
    "/convexity": Case(
        ({**ANNUAL_10, "yield_to_maturity": 0.10}, CONVEXITY_10),
        ({**ANNUAL_10, "coupon_rate": 0, "yield_to_maturity": 0}, 12.0),
        bad({**ANNUAL_10, "yield_to_maturity": -1.5}, INVALID),
    ),
    "/spread": Case(
        ({"bond_yield": 0.0825, "benchmark_yield": 0.064}, 0.0825 - 0.064),
        ({"bond_yield": 0.03, "benchmark_yield": 0.04}, -0.01),
        bad({"bond_yield": 0.0825}, V422),
    ),
    "/forward-rate": Case(
        (
            {
                "short_spot_rate": 0.05,
                "short_maturity": 1,
                "long_spot_rate": 0.06,
                "long_maturity": 2,
            },
            1.06**2 / 1.05 - 1,
        ),
        (
            {
                "short_spot_rate": 0.0,
                "short_maturity": 0,
                "long_spot_rate": 0.06,
                "long_maturity": 2,
            },
            0.06,
        ),
        bad(
            {
                "short_spot_rate": 0.05,
                "short_maturity": 2,
                "long_spot_rate": 0.06,
                "long_maturity": 1,
            },
            INVALID,
        ),
    ),
}

ENDPOINTS_BY_PATH = {endpoint.path: endpoint for endpoint in METRIC_ENDPOINTS}
PATHS = sorted(ENDPOINTS_BY_PATH)


def test_every_metric_endpoint_has_cases() -> None:
    assert set(CASES) == set(ENDPOINTS_BY_PATH)


def _check(body: dict[str, Any], path: str, expected: float) -> None:
    endpoint = ENDPOINTS_BY_PATH[path]
    assert body["metric"] == endpoint.metric
    assert body["unit"] == endpoint.unit.value
    assert body["value"] == pytest.approx(expected, rel=1e-10, abs=1e-12)


@pytest.mark.parametrize("path", PATHS)
def test_normal_case(client: TestClient, path: str) -> None:
    payload, expected = CASES[path].normal
    response = client.post(BASE + path, json=payload)
    assert response.status_code == 200, response.text
    _check(response.json(), path, expected)


@pytest.mark.parametrize("path", PATHS)
def test_edge_case(client: TestClient, path: str) -> None:
    payload, expected = CASES[path].edge
    response = client.post(BASE + path, json=payload)
    assert response.status_code == 200, response.text
    _check(response.json(), path, expected)


@pytest.mark.parametrize("path", PATHS)
def test_invalid_case(client: TestClient, path: str) -> None:
    payload, status, code = CASES[path].invalid
    response = client.post(BASE + path, json=payload)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_effective_rate_periodic_requires_frequency(client: TestClient) -> None:
    response = client.post(BASE + "/effective-rate", json={"nominal_rate": 0.12})
    assert response.status_code == 422
    assert "compounding_frequency" in response.json()["error"]["details"][0]["message"]


def test_modified_duration_semiannual_uses_periodic_yield(client: TestClient) -> None:
    macaulay = client.post(BASE + "/macaulay-duration", json={**SEMI, "yield_to_maturity": 0.08})
    modified = client.post(BASE + "/modified-duration", json={**SEMI, "yield_to_maturity": 0.08})
    assert modified.json()["value"] == pytest.approx(macaulay.json()["value"] / 1.04)
