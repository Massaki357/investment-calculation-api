"""Request → response tests for every technical indicator endpoint (normal / edge / invalid)."""

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.technical import CALCULATION_ENDPOINTS

BASE = "/api/v1/technical"
PRICES = [float(p) for p in range(1, 41)]
HIGH = [11.0, 12.0, 13.0, 12.0, 14.0]
LOW = [9.0, 10.0, 11.0, 10.0, 12.0]
CLOSE = [10.0, 11.0, 12.0, 11.0, 13.0]
HLC = {"high": HIGH, "low": LOW, "close": CLOSE}


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], str, list[Any] | None]
    edge: tuple[dict[str, Any], str, list[Any] | None]
    invalid: tuple[dict[str, Any], int, str]


V422 = (422, "VALIDATION_ERROR")
SHORT = (400, "INSUFFICIENT_DATA")
INVALID = (400, "INVALID_INPUT")


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


CASES: dict[str, Case] = {
    "/sma": Case(
        ({"prices": [1, 2, 3, 4, 5], "period": 3}, "values", [None, None, 2, 3, 4]),
        ({"prices": [3, 4], "period": 1}, "values", [3, 4]),
        bad({"prices": [1, 2], "period": 3}, SHORT),
    ),
    "/ema": Case(
        ({"prices": PRICES[:6], "period": 3}, "values", [None, None, 2, 3, 4, 5]),
        ({"prices": [7, 7, 7], "period": 3}, "values", [None, None, 7]),
        bad({"prices": [1, 2, -3], "period": 2}, V422),
    ),
    "/wma": Case(
        ({"prices": [1, 2, 3], "period": 3}, "values", [None, None, 14 / 6]),
        ({"prices": [5, 5], "period": 2}, "values", [None, 5]),
        bad({"prices": [1, 2, 3], "period": 0}, V422),
    ),
    "/vwma": Case(
        (
            {"prices": [10, 11, 12], "volumes": [100, 200, 100], "period": 3},
            "values",
            [None, None, 11],
        ),
        ({"prices": [10, 11, 12], "volumes": [0, 0, 5], "period": 2}, "values", [None, None, 12]),
        bad({"prices": [10, 11, 12], "volumes": [1, 2], "period": 2}, INVALID),
    ),
    "/rsi": Case(
        ({"prices": [10, 11, 10, 11, 10], "period": 2}, "values", [None, None, 50, 75, 37.5]),
        ({"prices": [1, 2, 3, 4], "period": 2}, "values", [None, None, 100, 100]),
        bad({"prices": [1, 2], "period": 2}, SHORT),
    ),
    "/macd": Case(
        (
            {"prices": PRICES, "fast_period": 3, "slow_period": 5, "signal_period": 2},
            "histogram",
            [None] * 5 + [0.0] * 35,
        ),
        (
            {"prices": PRICES[:6], "fast_period": 3, "slow_period": 5, "signal_period": 2},
            "macd",
            [None] * 4 + [1.0, 1.0],
        ),
        bad({"prices": PRICES, "fast_period": 5, "slow_period": 3}, INVALID),
    ),
    "/roc": Case(
        ({"prices": [100, 110, 121], "period": 1}, "values", [None, 0.1, 0.1]),
        ({"prices": [100, 50], "period": 1}, "values", [None, -0.5]),
        bad({"prices": [100], "period": 1}, SHORT),
    ),
    "/stochastic": Case(
        ({**HLC, "k_period": 3, "d_period": 2}, "percent_k", [None, None, 75, 100 / 3, 75]),
        (
            {"high": [10, 10], "low": [10, 10], "close": [10, 10], "k_period": 1, "d_period": 1},
            "percent_k",
            [None, None],
        ),
        bad({**HLC, "close": [10, 11, 12, 11, 15]}, INVALID),
    ),
    "/williams-r": Case(
        ({**HLC, "period": 3}, "values", [None, None, -25, -200 / 3, -25]),
        ({"high": [12], "low": [10], "close": [12], "period": 1}, "values", [0]),
        bad({**HLC, "low": [9, 10]}, INVALID),
    ),
    "/cci": Case(
        (
            {"high": [1, 2, 3], "low": [1, 2, 3], "close": [1, 2, 3], "period": 3},
            "values",
            [None, None, 100],
        ),
        ({"high": [2, 2], "low": [2, 2], "close": [2, 2], "period": 2}, "values", [None, None]),
        bad({**HLC, "period": 6}, SHORT),
    ),
    "/atr": Case(
        ({**HLC, "period": 2}, "values", [None, None, 2, 2, 2.5]),
        ({"high": [11, 11], "low": [9, 9], "close": [10, 10], "period": 1}, "values", [None, 2]),
        bad({**HLC, "period": 5}, SHORT),
    ),
    "/bollinger-bands": Case(
        ({"prices": [1, 2, 3], "period": 3}, "middle", [None, None, 2]),
        ({"prices": [5, 5, 5], "period": 3}, "percent_b", [None, None, None]),
        bad({"prices": [1, 2, 3], "period": 3, "standard_deviations": 0}, V422),
    ),
    "/historical-volatility": Case(
        ({"prices": [100, 100, 100], "period": 2}, "values", [None, None, 0]),
        ({"prices": [100, 200, 400], "period": 2}, "values", [None, None, 0]),
        bad({"prices": [100, 101, 102], "period": 1}, V422),
    ),
    "/obv": Case(
        (
            {"close": [10, 11, 11, 9], "volumes": [100, 200, 300, 400]},
            "values",
            [0, 200, 200, -200],
        ),
        ({"close": [10], "volumes": [100]}, "values", [0]),
        bad({"close": [10, 11], "volumes": [100, -1]}, V422),
    ),
    "/vwap": Case(
        ({"prices": [10, 11, 12], "volumes": [100, 0, 300]}, "values", [10, 10, 11.5]),
        ({"high": [12], "low": [9], "close": [9], "volumes": [10]}, "values", [10]),
        bad({"prices": [10], "high": [12], "low": [9], "close": [9], "volumes": [10]}, V422),
    ),
    "/money-flow-index": Case(
        ({**HLC, "volumes": [1000, 1100, 1200, 900, 1500], "period": 2}, "values", None),
        (
            {
                "high": [11, 12, 13],
                "low": [9, 10, 11],
                "close": [10, 11, 12],
                "volumes": [1, 1, 1],
                "period": 2,
            },
            "values",
            [None, None, 100],
        ),
        bad({**HLC, "volumes": [1000, 1100, 1200, 900, 1500], "period": 5}, SHORT),
    ),
}

ENDPOINTS_BY_PATH = {endpoint.path: endpoint for endpoint in CALCULATION_ENDPOINTS}
PATHS = sorted(ENDPOINTS_BY_PATH)


def test_every_endpoint_has_cases() -> None:
    assert set(CASES) == set(ENDPOINTS_BY_PATH)


def _check_series(body: dict[str, Any], field: str, expected: list[Any] | None) -> None:
    series = body[field]
    if expected is None:
        assert series[:2] == [None, None] and all(v is not None for v in series[2:])
        return
    assert len(series) == len(expected)
    for actual, wanted in zip(series, expected, strict=True):
        if wanted is None:
            assert actual is None
        else:
            assert actual == pytest.approx(wanted, abs=1e-9)


@pytest.mark.parametrize("path", PATHS)
def test_normal_case(client: TestClient, path: str) -> None:
    payload, field, expected = CASES[path].normal
    response = client.post(BASE + path, json=payload)
    assert response.status_code == 200, response.text
    _check_series(response.json(), field, expected)


@pytest.mark.parametrize("path", PATHS)
def test_edge_case(client: TestClient, path: str) -> None:
    payload, field, expected = CASES[path].edge
    response = client.post(BASE + path, json=payload)
    assert response.status_code == 200, response.text
    _check_series(response.json(), field, expected)


@pytest.mark.parametrize("path", PATHS)
def test_invalid_case(client: TestClient, path: str) -> None:
    payload, status, code = CASES[path].invalid
    response = client.post(BASE + path, json=payload)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_output_length_matches_input(client: TestClient) -> None:
    response = client.post(BASE + "/rsi", json={"prices": PRICES})
    body = response.json()
    assert len(body["values"]) == len(PRICES)
    assert body["latest"] == body["values"][-1]
    assert body["parameters"] == {"period": 14}


def test_bollinger_latest_bundle(client: TestClient) -> None:
    body = client.post(BASE + "/bollinger-bands", json={"prices": [1, 2, 3], "period": 3}).json()
    assert set(body["latest"]) == {"middle", "upper", "lower", "percent_b", "bandwidth"}
    assert body["latest"]["middle"] == pytest.approx(2)


def test_series_limit_applies_to_indicators(make_client: Any) -> None:
    limited = make_client(max_series_length=10)
    response = limited.post(BASE + "/sma", json={"prices": PRICES, "period": 3})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LIMIT_EXCEEDED"
