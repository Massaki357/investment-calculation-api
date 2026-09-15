"""Safety limits: request body size, calculation time budget and malformed or oversized input."""

from collections.abc import Iterator

from fastapi.testclient import TestClient

from tests.conftest import ClientFactory, SettingsFactory

RATIO = "/_test/ratio"
MIN_VARIANCE = "/api/v1/portfolio/minimum-variance"
COV2 = [[0.04, 0.03], [0.03, 0.09]]


def _error_code(response_json: dict) -> str:
    return response_json["error"]["code"]


class TestBodySizeLimit:
    def test_declared_content_length_over_limit_returns_413(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(max_request_body_bytes=40)

        response = client.post(RATIO, json={"numerator": 1.0, "denominator": 2.0, "x": "y" * 50})

        assert response.status_code == 413
        assert _error_code(response.json()) == "PAYLOAD_TOO_LARGE"
        assert "40 bytes" in response.json()["error"]["message"]
        assert "X-Request-ID" in response.headers

    def test_streamed_body_over_limit_returns_413(self, make_client: ClientFactory) -> None:
        client = make_client(max_request_body_bytes=40)

        def chunks() -> Iterator[bytes]:
            yield b'{"numerator": 1, '
            yield b'"denominator": 2, "padding": "' + b"y" * 50 + b'"}'

        response = client.post(
            RATIO, content=chunks(), headers={"Content-Type": "application/json"}
        )

        assert "content-length" not in {key.lower() for key in response.request.headers}
        assert response.status_code == 413
        assert _error_code(response.json()) == "PAYLOAD_TOO_LARGE"

    def test_body_within_limit_is_processed(self, make_client: ClientFactory) -> None:
        client = make_client(max_request_body_bytes=40)

        response = client.post(RATIO, json={"numerator": 1.0, "denominator": 2.0})

        assert response.status_code == 200
        assert response.json()["value"] == 0.5

    def test_default_limit_is_10_mib(self, make_settings: SettingsFactory) -> None:
        assert make_settings().max_request_body_bytes == 10 * 1024 * 1024


class TestMalformedBody:
    def test_unparseable_body_returns_malformed_request(self, client: TestClient) -> None:
        # Valid JSON syntax, but nested deeper than the parser's recursion limit.
        body = "[" * 100_000 + "]" * 100_000

        response = client.post(RATIO, content=body, headers={"Content-Type": "application/json"})

        assert response.status_code == 400
        assert _error_code(response.json()) == "MALFORMED_REQUEST"

    def test_ragged_covariance_matrix_is_invalid_input(self, client: TestClient) -> None:
        response = client.post(MIN_VARIANCE, json={"covariance_matrix": [[0.04, 0.01], [0.01]]})

        assert response.status_code == 400
        assert _error_code(response.json()) == "INVALID_INPUT"

    def test_returns_matrix_columns_are_capped(self, client: TestClient) -> None:
        response = client.post(MIN_VARIANCE, json={"returns": [[0.01] * 501, [0.02] * 501]})

        assert response.status_code == 422
        assert response.json()["error"]["details"][0]["field"] == "body.returns.0"

    def test_covariance_matrix_rows_are_capped(self, client: TestClient) -> None:
        response = client.post(MIN_VARIANCE, json={"covariance_matrix": [[0.04] * 501]})

        assert response.status_code == 422


class TestCalculationTimeBudget:
    def test_optimization_over_budget_returns_limit_exceeded(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(max_calculation_seconds=1e-9)

        response = client.post(MIN_VARIANCE, json={"covariance_matrix": COV2})

        assert response.status_code == 400
        assert _error_code(response.json()) == "LIMIT_EXCEEDED"
        assert "time limit" in response.json()["error"]["message"]

    def test_monte_carlo_over_budget_returns_limit_exceeded(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(max_calculation_seconds=1e-9)
        payload = {
            "initial_value": 100,
            "expected_return": 0.1,
            "volatility": 0.2,
            "periods": 10,
            "simulations": 10,
            "seed": 1,
        }

        response = client.post("/api/v1/scenarios/monte-carlo", json=payload)

        assert response.status_code == 400
        assert _error_code(response.json()) == "LIMIT_EXCEEDED"

    def test_sensitivity_aborts_instead_of_reporting_per_cell_errors(
        self, make_client: ClientFactory
    ) -> None:
        client = make_client(max_calculation_seconds=1e-9)
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": {"current_dividend": 2, "cost_of_equity": 0.10, "growth_rate": 0.05},
            "variables": [{"name": "growth_rate", "values": [0.01, 0.02]}],
        }

        response = client.post("/api/v1/scenarios/sensitivity-analysis", json=payload)

        assert response.status_code == 400
        assert _error_code(response.json()) == "LIMIT_EXCEEDED"

    def test_fast_calculation_within_default_budget(self, client: TestClient) -> None:
        response = client.post(MIN_VARIANCE, json={"covariance_matrix": COV2})

        assert response.status_code == 200
