"""Request → response tests for risk and risk-adjusted performance endpoints."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.risk import METRIC_ENDPOINTS

BASE = "/api/v1/risk"
ASSET = [0.012, -0.008, 0.015, -0.021, 0.009, 0.004, -0.013, 0.018, 0.007, -0.005]
BENCH = [0.010, -0.006, 0.011, -0.018, 0.007, 0.005, -0.010, 0.014, 0.006, -0.004]
PAIRED = {"asset_returns": ASSET, "benchmark_returns": BENCH}
V422 = (422, "VALIDATION_ERROR")
DIV0 = (400, "DIVISION_BY_ZERO")
INVALID = (400, "INVALID_INPUT")


def beta_of(asset: list[float], bench: list[float]) -> float:
    return float(np.cov(asset, bench, ddof=1)[0, 1] / np.var(bench, ddof=1))


def annualized(returns: list[float], ppy: int = 252) -> float:
    return float(np.prod(1 + np.array(returns)) ** (ppy / len(returns)) - 1)


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


RF_P = 1.05 ** (1 / 252) - 1
EXCESS = np.array(ASSET) - RF_P

CASES: dict[str, Case] = {
    "/cumulative-return": Case(
        ({"prices": [100, 104, 97, 108]}, 0.08),
        ({"returns": [math.log(1.1), math.log(0.9)], "return_type": "log"}, -0.01),
        bad({"returns": [0.1, -1.0]}, INVALID),
    ),
    "/annualized-return": Case(
        ({"returns": [0.01] * 12, "periods_per_year": 12}, 1.01**12 - 1),
        ({"returns": [0.01] * 6, "periods_per_year": 12}, 1.01**12 - 1),
        bad({"returns": [0.01] * 6, "periods_per_year": 0}, V422),
    ),
    "/standard-deviation": Case(
        ({"returns": ASSET}, float(np.std(ASSET, ddof=1))),
        ({"returns": ASSET, "population": True}, float(np.std(ASSET, ddof=0))),
        bad({"returns": ASSET, "prices": [100, 101, 102]}, V422),
    ),
    "/beta": Case(
        (PAIRED, beta_of(ASSET, BENCH)),
        ({"asset_returns": [2 * b for b in BENCH], "benchmark_returns": BENCH}, 2.0),
        bad({"asset_returns": ASSET, "benchmark_returns": [0.01] * 10}, DIV0),
    ),
    "/correlation": Case(
        (PAIRED, float(np.corrcoef(ASSET, BENCH)[0, 1])),
        ({"asset_returns": [-b for b in BENCH], "benchmark_returns": BENCH}, -1.0),
        bad({"asset_returns": ASSET, "benchmark_returns": BENCH[:-1]}, INVALID),
    ),
    "/covariance": Case(
        (PAIRED, float(np.cov(ASSET, BENCH, ddof=1)[0, 1])),
        ({**PAIRED, "population": True}, float(np.cov(ASSET, BENCH, ddof=0)[0, 1])),
        bad({"asset_returns": ASSET}, V422),
    ),
    "/r-squared": Case(
        (PAIRED, float(np.corrcoef(ASSET, BENCH)[0, 1] ** 2)),
        ({"asset_returns": [3 * b for b in BENCH], "benchmark_returns": BENCH}, 1.0),
        bad({"asset_returns": [0.01] * 10, "benchmark_returns": BENCH}, DIV0),
    ),
    "/sharpe": Case(
        (
            {"returns": ASSET, "risk_free_rate": 0.05},
            float(EXCESS.mean() / EXCESS.std(ddof=1) * math.sqrt(252)),
        ),
        (
            {"returns": ASSET},
            float(np.mean(ASSET) / np.std(ASSET, ddof=1) * math.sqrt(252)),
        ),
        bad({"returns": [0.01, 0.01, 0.01]}, DIV0),
    ),
    "/sortino": Case(
        (
            {"returns": ASSET},
            float(
                np.mean(ASSET)
                / math.sqrt(np.mean(np.minimum(np.array(ASSET), 0) ** 2))
                * math.sqrt(252)
            ),
        ),
        (
            {"returns": ASSET, "risk_free_rate": 0.05, "minimum_acceptable_return": 0},
            float(
                np.mean(ASSET)
                / math.sqrt(np.mean(np.minimum(np.array(ASSET), 0) ** 2))
                * math.sqrt(252)
            ),
        ),
        bad({"returns": [0.01, 0.02]}, DIV0),
    ),
    "/treynor": Case(
        ({**PAIRED, "risk_free_rate": 0.05}, (annualized(ASSET) - 0.05) / beta_of(ASSET, BENCH)),
        ({**PAIRED, "risk_free_rate": 0}, annualized(ASSET) / beta_of(ASSET, BENCH)),
        bad({**PAIRED, "risk_free_rate": -1}, V422),
    ),
    "/calmar": Case(
        ({"returns": [0.1, -0.2, 0.3], "periods_per_year": 1}, (1.144 ** (1 / 3) - 1) / 0.2),
        ({"prices": [100, 110, 88, 114.4], "periods_per_year": 1}, (1.144 ** (1 / 3) - 1) / 0.2),
        bad({"returns": [0.01, 0.02]}, DIV0),
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
    assert body["value"] == pytest.approx(expected, rel=1e-9, abs=1e-12)


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


def post(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(BASE + path, json=payload)


def components(body: dict[str, Any]) -> dict[str, float]:
    return {item["metric"]: item["value"] for item in body["components"]}


class TestReturnsAndDispersion:
    def test_returns_from_prices(self, client: TestClient) -> None:
        data = post(client, "/returns", {"prices": [100, 110, 99]}).json()
        assert data["returns"] == pytest.approx([0.1, -0.1])
        assert data["observations"] == 2

    def test_log_returns_edge(self, client: TestClient) -> None:
        data = post(client, "/returns", {"prices": [100, 110], "return_type": "log"}).json()
        assert data["returns"] == pytest.approx([math.log(1.1)])

    def test_returns_reject_non_positive_prices(self, client: TestClient) -> None:
        assert post(client, "/returns", {"prices": [100, 0]}).status_code == 422

    def test_volatility(self, client: TestClient) -> None:
        data = post(client, "/volatility", {"returns": ASSET, "periods_per_year": 252}).json()
        periodic = float(np.std(ASSET, ddof=1))
        assert data["value"] == pytest.approx(periodic * math.sqrt(252))
        assert components(data)["Periodic Volatility"] == pytest.approx(periodic)

    def test_variance(self, client: TestClient) -> None:
        data = post(client, "/variance", {"returns": ASSET, "periods_per_year": 12}).json()
        assert data["value"] == pytest.approx(np.var(ASSET, ddof=1))
        assert components(data)["Annualized Variance"] == pytest.approx(np.var(ASSET, ddof=1) * 12)

    def test_downside_deviation(self, client: TestClient) -> None:
        data = post(client, "/downside-deviation", {"returns": [0.02, -0.01, 0.03, -0.02]}).json()
        periodic = math.sqrt((0.01**2 + 0.02**2) / 4)
        assert data["value"] == pytest.approx(periodic * math.sqrt(252))

    def test_series_limit_is_enforced(self, make_client: Any) -> None:
        limited = make_client(max_series_length=5)
        response = limited.post(BASE + "/volatility", json={"returns": ASSET})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "LIMIT_EXCEEDED"


class TestAlphaAndTail:
    def test_alpha(self, client: TestClient) -> None:
        asset = [0.0002 + 1.5 * b for b in BENCH]
        data = post(client, "/alpha", {"asset_returns": asset, "benchmark_returns": BENCH}).json()
        assert data["value"] == pytest.approx(0.0002 * 252)
        assert components(data)["Beta"] == pytest.approx(1.5)

    def test_maximum_drawdown_from_prices(self, client: TestClient) -> None:
        data = post(client, "/maximum-drawdown", {"prices": [100, 120, 90, 95, 130, 80, 85]}).json()
        assert data["max_drawdown"] == pytest.approx(80 / 130 - 1)
        assert (data["peak_index"], data["trough_index"]) == (4, 5)
        assert data["recovery_index"] is None

    def test_maximum_drawdown_from_returns_uses_wealth_index(self, client: TestClient) -> None:
        data = post(client, "/maximum-drawdown", {"returns": [0.1, -0.2, 0.3]}).json()
        assert data["max_drawdown"] == pytest.approx(-0.2)
        assert (data["peak_index"], data["trough_index"], data["recovery_index"]) == (1, 2, 3)

    def test_historical_var(self, client: TestClient) -> None:
        ladder = [-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        data = post(client, "/var/historical", {"returns": ladder, "confidence": 0.9}).json()
        assert data["value"] == pytest.approx(0.032)
        assert components(data)["Confidence"] == 0.9

    def test_parametric_var_ten_day(self, client: TestClient) -> None:
        payload = {"returns": ASSET, "confidence": 0.99, "horizon_periods": 10}
        data = post(client, "/var/parametric", payload).json()
        mu, sigma, z = np.mean(ASSET), np.std(ASSET, ddof=1), 2.3263478740408408
        assert data["value"] == pytest.approx(-(mu * 10 - z * sigma * math.sqrt(10)))

    @pytest.mark.parametrize("path", ["/cvar", "/expected-shortfall"])
    def test_cvar_and_expected_shortfall_are_identical(self, client: TestClient, path: str) -> None:
        ladder = [-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        data = post(client, path, {"returns": ladder, "confidence": 0.9}).json()
        assert data["value"] == pytest.approx(0.05)
        assert components(data)["VaR (historical)"] == pytest.approx(0.032)

    def test_confidence_out_of_range(self, client: TestClient) -> None:
        assert (
            post(client, "/var/historical", {"returns": ASSET, "confidence": 0.4}).status_code
            == 422
        )


class TestRiskAdjustedStructured:
    def test_information_ratio(self, client: TestClient) -> None:
        data = post(client, "/information-ratio", PAIRED).json()
        active = np.array(ASSET) - np.array(BENCH)
        assert data["value"] == pytest.approx(active.mean() / active.std(ddof=1) * math.sqrt(252))
        assert components(data)["Tracking Error"] == pytest.approx(
            active.std(ddof=1) * math.sqrt(252)
        )

    def test_jensens_alpha_of_benchmark_is_zero(self, client: TestClient) -> None:
        payload = {"asset_returns": BENCH, "benchmark_returns": BENCH, "risk_free_rate": 0.05}
        data = post(client, "/jensens-alpha", payload).json()
        assert data["value"] == pytest.approx(0, abs=1e-12)
        assert components(data)["Beta"] == pytest.approx(1.0)

    def test_m2(self, client: TestClient) -> None:
        data = post(client, "/m2", {**PAIRED, "risk_free_rate": 0.05}).json()
        sigma_m = float(np.std(BENCH, ddof=1)) * math.sqrt(252)
        assert data["value"] == pytest.approx(components(data)["Sharpe Ratio"] * sigma_m + 0.05)

    def test_paired_prices_are_converted(self, client: TestClient) -> None:
        prices_a = [100, 102, 101, 104, 103]
        prices_b = [50, 50.5, 50.2, 51.0, 50.8]
        data = post(
            client, "/information-ratio", {"asset_prices": prices_a, "benchmark_prices": prices_b}
        )
        assert data.status_code == 200

    def test_paired_requires_one_source_per_side(self, client: TestClient) -> None:
        payload = {**PAIRED, "asset_prices": [100, 101, 102]}
        assert post(client, "/m2", payload).status_code == 422
