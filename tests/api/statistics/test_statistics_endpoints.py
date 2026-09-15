"""Request → response tests for statistics endpoints."""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy import stats

from app.api.v1.routes.statistics import METRIC_ENDPOINTS

BASE = "/api/v1/statistics"
CLASSIC = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
SKEWED = [1.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 9.0, 15.0]
X = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
Y = [2.3, 3.8, 6.4, 7.7, 10.4, 11.9, 14.2]
V422 = (422, "VALIDATION_ERROR")
DIV0 = (400, "DIVISION_BY_ZERO")
INSUFFICIENT = (400, "INSUFFICIENT_DATA")
INVALID = (400, "INVALID_INPUT")


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


CASES: dict[str, Case] = {
    "/mean": Case(
        ({"values": CLASSIC}, 5.0),
        ({"values": [-3.5]}, -3.5),
        bad({"values": []}, V422),
    ),
    "/median": Case(
        ({"values": CLASSIC}, 4.5),
        ({"values": [3.0, 1.0, 2.0]}, 2.0),
        bad({"values": "1,2,3"}, V422),
    ),
    "/variance": Case(
        ({"values": CLASSIC}, 32 / 7),
        ({"values": CLASSIC, "population": True}, 4.0),
        bad({"values": [5.0]}, INSUFFICIENT),
    ),
    "/standard-deviation": Case(
        ({"values": CLASSIC, "population": True}, 2.0),
        ({"values": [5.0], "population": True}, 0.0),
        bad({"values": [5.0]}, INSUFFICIENT),
    ),
    "/skewness": Case(
        ({"values": SKEWED}, float(stats.skew(SKEWED, bias=False))),
        ({"values": [1.0, 2.0, 3.0, 4.0, 5.0]}, 0.0),
        bad({"values": [2.0, 2.0, 2.0]}, DIV0),
    ),
    "/kurtosis": Case(
        ({"values": SKEWED}, float(stats.kurtosis(SKEWED, fisher=True, bias=False))),
        (
            {"values": SKEWED, "excess": False, "bias_corrected": False},
            float(stats.kurtosis(SKEWED, fisher=False, bias=True)),
        ),
        bad({"values": [1.0, 2.0, 4.0]}, INSUFFICIENT),
    ),
    "/covariance": Case(
        ({"x": X, "y": Y}, float(np.cov(X, Y, ddof=1)[0, 1])),
        ({"x": X, "y": Y, "population": True}, float(np.cov(X, Y, ddof=0)[0, 1])),
        bad({"x": X, "y": Y[:-1]}, INVALID),
    ),
    "/correlation": Case(
        ({"x": X, "y": Y}, float(np.corrcoef(X, Y)[0, 1])),
        ({"x": X, "y": [-x for x in X]}, -1.0),
        bad({"x": X, "y": [1.0] * len(X)}, DIV0),
    ),
    "/r-squared": Case(
        ({"x": X, "y": Y}, float(np.corrcoef(X, Y)[0, 1] ** 2)),
        ({"x": X, "y": [2 * x + 1 for x in X]}, 1.0),
        bad({"x": [1.0]}, V422),
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


class TestStructuredStatistics:
    def test_percentiles(self, client: TestClient) -> None:
        data = post(client, "/percentiles", {"values": SKEWED, "percentiles": [10, 50, 90]}).json()
        values = [item["value"] for item in data["percentiles"]]
        assert values == pytest.approx(np.percentile(SKEWED, [10, 50, 90]))
        assert [item["percentile"] for item in data["percentiles"]] == [10, 50, 90]

    def test_percentiles_nearest_method_edge(self, client: TestClient) -> None:
        payload = {"values": SKEWED, "percentiles": [33], "method": "nearest"}
        data = post(client, "/percentiles", payload).json()
        assert data["percentiles"][0]["value"] == np.percentile(SKEWED, 33, method="nearest")

    def test_percentile_rank_out_of_range(self, client: TestClient) -> None:
        payload = {"values": SKEWED, "percentiles": [120]}
        assert post(client, "/percentiles", payload).status_code == 422

    def test_quartiles(self, client: TestClient) -> None:
        data = post(client, "/quartiles", {"values": [1, 2, 3, 4, 5, 6, 7, 8, 9]}).json()
        assert (data["q1"], data["q2"], data["q3"], data["interquartile_range"]) == (3, 5, 7, 4)

    def test_z_score(self, client: TestClient) -> None:
        payload = {"values": CLASSIC, "observation": 11, "population": True}
        data = post(client, "/z-score", payload).json()
        assert data["mean"] == 5
        assert data["standard_deviation"] == pytest.approx(2)
        assert data["observation_z_score"] == pytest.approx(3)
        assert len(data["z_scores"]) == len(CLASSIC)

    def test_z_score_constant_values(self, client: TestClient) -> None:
        response = post(client, "/z-score", {"values": [1, 1, 1]})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DIVISION_BY_ZERO"

    def test_confidence_interval(self, client: TestClient) -> None:
        data = post(client, "/confidence-interval", {"values": SKEWED, "confidence": 0.95}).json()
        sem = np.std(SKEWED, ddof=1) / math.sqrt(len(SKEWED))
        lower, upper = stats.t.interval(0.95, len(SKEWED) - 1, loc=np.mean(SKEWED), scale=sem)
        assert data["lower"] == pytest.approx(lower)
        assert data["upper"] == pytest.approx(upper)
        assert data["degrees_of_freedom"] == 8

    def test_confidence_interval_bounds(self, client: TestClient) -> None:
        payload = {"values": SKEWED, "confidence": 1}
        assert post(client, "/confidence-interval", payload).status_code == 422

    def test_linear_regression_matches_scipy(self, client: TestClient) -> None:
        data = post(client, "/linear-regression", {"x": X, "y": Y}).json()
        reference: Any = stats.linregress(X, Y)  # SciPy stubs omit the result attributes
        assert data["slope"] == pytest.approx(reference.slope)
        assert data["intercept"] == pytest.approx(reference.intercept)
        assert data["slope_standard_error"] == pytest.approx(reference.stderr)
        assert data["slope_p_value"] == pytest.approx(reference.pvalue)

    def test_linear_regression_perfect_fit_edge(self, client: TestClient) -> None:
        data = post(client, "/linear-regression", {"x": [1, 2, 3], "y": [3, 5, 7]}).json()
        assert data["slope"] == pytest.approx(2)
        assert data["slope_t_statistic"] is None

    def test_linear_regression_too_few_points(self, client: TestClient) -> None:
        response = post(client, "/linear-regression", {"x": [1, 2], "y": [3, 5]})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"
