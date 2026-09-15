"""Request → response tests for portfolio analytics and construction endpoints."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.portfolio import METRIC_ENDPOINTS

BASE = "/api/v1/portfolio"
COV2 = [[0.04, 0.03], [0.03, 0.09]]
MU2 = [0.10, 0.15]
COV3 = [[0.04, 0.006, 0.002], [0.006, 0.09, 0.018], [0.002, 0.018, 0.0225]]
MU3 = [0.08, 0.14, 0.06]
RETURNS = [[0.01, 0.02], [0.03, -0.01], [-0.02, 0.01], [0.01, 0.00], [0.02, 0.01]]
BENCH = [0.012, 0.01, -0.005, 0.004, 0.015]
V422 = (422, "VALIDATION_ERROR")
INVALID = (400, "INVALID_INPUT")


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


def portfolio_series(weights: list[float]) -> np.ndarray:
    return np.array(RETURNS) @ np.array(weights)


SERIES = portfolio_series([0.6, 0.4])
ACTIVE = SERIES - np.array(BENCH)

CASES: dict[str, Case] = {
    "/expected-return": Case(
        ({"weights": [0.6, 0.4], "expected_returns": MU2}, 0.12),
        (
            {"weights": [0.6, 0.4], "returns": RETURNS, "periods_per_year": 12},
            float(np.array(RETURNS).mean(axis=0) @ np.array([0.6, 0.4]) * 12),
        ),
        bad({"weights": [0.6, 0.3], "expected_returns": MU2}, INVALID),
    ),
    "/variance": Case(
        ({"weights": [0.6, 0.4], "covariance_matrix": COV2}, 0.0432),
        ({"weights": [1.0, 0.0], "covariance_matrix": COV2}, 0.04),
        bad({"weights": [0.6, 0.4], "covariance_matrix": [[0.04, 0.5], [0.5, 0.09]]}, INVALID),
    ),
    "/volatility": Case(
        ({"weights": [0.6, 0.4], "covariance_matrix": COV2}, math.sqrt(0.0432)),
        # 1.69 × 0.04 + 0.09 × 0.09 − 2 × 0.39 × 0.03 = 0.0523
        ({"weights": [1.3, -0.3], "covariance_matrix": COV2}, math.sqrt(0.0523)),
        bad({"weights": [0.6, 0.4], "covariance_matrix": COV2, "returns": RETURNS}, V422),
    ),
    "/beta": Case(
        ({"weights": [0.5, 0.3, 0.2], "asset_betas": [1.1, 0.2, 0.8]}, 0.77),
        (
            {"weights": [0.6, 0.4], "returns": RETURNS, "benchmark_returns": BENCH},
            float(np.cov(SERIES, BENCH, ddof=1)[0, 1] / np.var(BENCH, ddof=1)),
        ),
        bad({"weights": [0.6, 0.4], "returns": RETURNS}, V422),
    ),
    "/tracking-error": Case(
        (
            {"weights": [0.6, 0.4], "returns": RETURNS, "benchmark_returns": BENCH},
            float(ACTIVE.std(ddof=1) * math.sqrt(252)),
        ),
        (
            {
                "method": "ex_ante",
                "weights": [0.6, 0.4],
                "benchmark_weights": [0.6, 0.4],
                "covariance_matrix": COV2,
            },
            0.0,
        ),
        bad({"method": "ex_ante", "weights": [0.6, 0.4], "covariance_matrix": COV2}, V422),
    ),
    "/turnover": Case(
        ({"current_weights": [0.5, 0.3, 0.2], "target_weights": [0.4, 0.4, 0.2]}, 0.1),
        ({"current_weights": [1.0, 0.0], "target_weights": [0.0, 1.0]}, 1.0),
        bad({"current_weights": [1.0], "target_weights": [0.5, 0.5]}, INVALID),
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


def weights_of(body: dict[str, Any]) -> list[float]:
    return [item["weight"] for item in body["weights"]]


class TestAnalyticsStructured:
    def test_portfolio_return(self, client: TestClient) -> None:
        data = post(client, "/return", {"weights": [0.6, 0.4], "returns": RETURNS}).json()
        assert data["portfolio_returns"] == pytest.approx(SERIES)
        assert data["cumulative_return"] == pytest.approx(np.prod(1 + SERIES) - 1)
        assert data["periods"] == 5

    def test_covariance_matrix(self, client: TestClient) -> None:
        payload = {"returns": RETURNS, "periods_per_year": 252, "asset_names": ["a", "b"]}
        data = post(client, "/covariance", payload).json()
        assert data["assets"] == ["a", "b"]
        assert data["matrix"] == pytest.approx(np.cov(np.array(RETURNS).T, ddof=1) * 252)

    def test_correlation_matrix_from_covariance(self, client: TestClient) -> None:
        data = post(client, "/correlation", {"covariance_matrix": COV2}).json()
        assert data["assets"] == ["asset_1", "asset_2"]
        assert np.array(data["matrix"]) == pytest.approx(np.array([[1, 0.5], [0.5, 1]]))

    def test_asset_names_length_mismatch(self, client: TestClient) -> None:
        response = post(client, "/correlation", {"covariance_matrix": COV2, "asset_names": ["a"]})
        assert response.status_code == 400

    def test_alpha(self, client: TestClient) -> None:
        payload = {"weights": [0.6, 0.4], "returns": RETURNS, "benchmark_returns": BENCH}
        data = post(client, "/alpha", payload).json()
        components = {c["metric"]: c["value"] for c in data["components"]}
        expected = components["Portfolio Annualized Return"] - (
            components["Portfolio Beta"] * components["Benchmark Annualized Return"]
        )
        assert data["value"] == pytest.approx(expected)

    def test_risk_contribution(self, client: TestClient) -> None:
        payload = {"weights": [0.6, 0.4], "covariance_matrix": COV2, "asset_names": ["x", "y"]}
        data = post(client, "/risk-contribution", payload).json()
        assert data["volatility"] == pytest.approx(math.sqrt(0.0432))
        shares = [item["percent_contribution"] for item in data["contributions"]]
        assert shares == pytest.approx([0.5, 0.5])
        assert [item["asset"] for item in data["contributions"]] == ["x", "y"]

    def test_concentration(self, client: TestClient) -> None:
        data = post(client, "/concentration", {"weights": [0.5, 0.3, 0.2]}).json()
        assert data["hhi"] == pytest.approx(0.38)
        assert data["effective_number_of_assets"] == pytest.approx(1 / 0.38)

    def test_concentration_rejects_shorts(self, client: TestClient) -> None:
        response = post(client, "/concentration", {"weights": [1.2, -0.2]})
        assert response.status_code == 400


class TestConstruction:
    def test_minimum_variance(self, client: TestClient) -> None:
        data = post(client, "/minimum-variance", {"covariance_matrix": COV2}).json()
        assert weights_of(data) == pytest.approx([6 / 7, 1 / 7], abs=1e-7)
        assert data["expected_return"] is None
        assert data["variance"] == pytest.approx(data["volatility"] ** 2)

    def test_minimum_variance_with_bounds_edge(self, client: TestClient) -> None:
        payload = {"covariance_matrix": COV2, "expected_returns": MU2, "max_weight": 0.7}
        data = post(client, "/minimum-variance", payload).json()
        assert weights_of(data) == pytest.approx([0.7, 0.3], abs=1e-7)
        assert data["expected_return"] == pytest.approx(0.115, abs=1e-8)

    def test_infeasible_bounds(self, client: TestClient) -> None:
        payload = {"covariance_matrix": COV3, "max_weight": 0.3}
        response = post(client, "/minimum-variance", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"

    def test_maximum_sharpe(self, client: TestClient) -> None:
        payload = {"covariance_matrix": COV2, "expected_returns": MU2, "risk_free_rate": 0.03}
        data = post(client, "/maximum-sharpe", payload).json()
        assert weights_of(data) == pytest.approx([0.5, 0.5], abs=1e-6)
        sigma = math.sqrt(0.25 * 0.04 + 0.25 * 0.09 + 2 * 0.25 * 0.03)
        assert data["sharpe_ratio"] == pytest.approx((0.125 - 0.03) / sigma, rel=1e-6)

    def test_maximum_sharpe_requires_expected_returns(self, client: TestClient) -> None:
        assert post(client, "/maximum-sharpe", {"covariance_matrix": COV2}).status_code == 422

    def test_efficient_frontier(self, client: TestClient) -> None:
        payload = {"covariance_matrix": COV3, "expected_returns": MU3, "points": 6}
        data = post(client, "/efficient-frontier", payload).json()
        returns = [point["expected_return"] for point in data["points"]]
        vols = [point["volatility"] for point in data["points"]]
        assert len(data["points"]) == 6
        assert returns == sorted(returns) and vols == sorted(vols)
        assert returns[-1] == pytest.approx(0.14)

    def test_frontier_rejects_expected_returns_with_returns_matrix(
        self, client: TestClient
    ) -> None:
        payload = {"returns": RETURNS, "expected_returns": MU2}
        assert post(client, "/efficient-frontier", payload).status_code == 422

    def test_risk_parity(self, client: TestClient) -> None:
        data = post(client, "/risk-parity", {"covariance_matrix": COV3}).json()
        shares = [item["percent_contribution"] for item in data["risk_contributions"]]
        assert shares == pytest.approx([1 / 3] * 3, abs=1e-8)
        assert sum(weights_of(data)) == pytest.approx(1)

    def test_inverse_volatility(self, client: TestClient) -> None:
        data = post(client, "/inverse-volatility", {"covariance_matrix": COV2}).json()
        assert weights_of(data) == pytest.approx([0.6, 0.4])
        assert data["risk_contributions"] is not None

    def test_construction_from_returns_matrix(self, client: TestClient) -> None:
        data = post(client, "/risk-parity", {"returns": RETURNS, "asset_names": ["a", "b"]})
        assert data.status_code == 200
        assert [item["asset"] for item in data.json()["weights"]] == ["a", "b"]
