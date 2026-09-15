"""Request → response tests for scenario analysis, stress testing and Monte Carlo."""

import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/scenarios"
GORDON = {"current_dividend": 2, "cost_of_equity": 0.10, "growth_rate": 0.05}
DCF = {
    "cash_flows": [100, 110, 121],
    "discount_rate": 0.10,
    "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
    "net_debt": 300,
    "shares_outstanding": 100,
}
MONTE_CARLO = {
    "initial_value": 100000,
    "expected_return": 0.10,
    "volatility": 0.20,
    "periods": 252,
    "simulations": 10000,
    "seed": 42,
}


def post(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(BASE + path, json=payload)


def gordon(cost_of_equity: float, growth: float) -> float:
    return 2 * (1 + growth) / (cost_of_equity - growth)


class TestModels:
    def test_models_endpoint_lists_registered_calculations(self, client: TestClient) -> None:
        models = client.get(BASE + "/models").json()
        ids = [item["model"] for item in models]
        assert "valuation/dcf/fcff" in ids and "technical/rsi" in ids
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))


class TestSensitivity:
    def test_one_variable(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "variables": [{"name": "growth_rate", "values": [0.03, 0.04]}],
        }
        data = post(client, "/sensitivity-analysis", payload).json()

        assert data["base_output"] == pytest.approx(gordon(0.10, 0.05))
        assert [p["output"] for p in data["points"]] == pytest.approx(
            [gordon(0.10, 0.03), gordon(0.10, 0.04)]
        )
        assert data["table"] is None

    def test_two_variable_grid_with_invalid_cell(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "variables": [
                {"name": "cost_of_equity", "values": [0.05, 0.10]},
                {"name": "growth_rate", "values": [0.03, 0.05]},
            ],
        }
        data = post(client, "/sensitivity-analysis", payload).json()

        assert data["table"][0][0] == pytest.approx(gordon(0.05, 0.03))
        assert data["table"][0][1] is None
        assert data["table"][1] == pytest.approx([gordon(0.10, 0.03), gordon(0.10, 0.05)])
        errors = [p["error"] for p in data["points"]]
        assert errors[1]["code"] == "INVALID_INPUT"
        assert errors[0] is None

    def test_nested_input_path(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/dcf/fcff",
            "output": "enterprise_value",
            "base_inputs": DCF,
            "variables": [{"name": "terminal.growth_rate", "values": [0.02]}],
        }
        data = post(client, "/sensitivity-analysis", payload).json()
        expected = 3 * 100 / 1.1 + (121 * 1.02 / 0.08) / 1.331
        assert data["points"][0]["output"] == pytest.approx(expected)

    def test_invalid_base_inputs(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": {"current_dividend": 2},
            "variables": [{"name": "growth_rate", "values": [0.03]}],
        }
        response = post(client, "/sensitivity-analysis", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.parametrize(
        ("change", "status"),
        [
            ({"model": "valuation/not-a-model"}, 400),
            ({"output": "does_not_exist"}, 400),
            ({"model": "import os"}, 422),
            ({"variables": []}, 422),
        ],
    )
    def test_rejections(self, client: TestClient, change: dict[str, Any], status: int) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "variables": [{"name": "growth_rate", "values": [0.03]}],
            **change,
        }
        assert post(client, "/sensitivity-analysis", payload).status_code == status

    def test_grid_limit(self, client: TestClient) -> None:
        values = [0.01 + i * 0.0001 for i in range(100)]
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "variables": [
                {"name": "cost_of_equity", "values": [0.2 + v for v in values]},
                {"name": "growth_rate", "values": values},
            ],
        }
        response = post(client, "/sensitivity-analysis", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "LIMIT_EXCEEDED"


class TestScenarioAnalysis:
    def test_bear_base_bull_with_probabilities(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "scenarios": [
                {"name": "bear", "probability": 0.25, "overrides": {"growth_rate": 0.03}},
                {"name": "base", "probability": 0.5},
                {"name": "bull", "probability": 0.25, "overrides": {"growth_rate": 0.06}},
            ],
        }
        data = post(client, "/scenario-analysis", payload).json()

        values = [gordon(0.10, 0.03), gordon(0.10, 0.05), gordon(0.10, 0.06)]
        assert [s["output"] for s in data["scenarios"]] == pytest.approx(values)
        assert data["scenarios"][0]["difference_from_base"] == pytest.approx(values[0] - values[1])
        assert data["probability_weighted_output"] == pytest.approx(
            0.25 * values[0] + 0.5 * values[1] + 0.25 * values[2]
        )
        assert data["minimum_output"] == pytest.approx(values[0])
        assert data["maximum_output"] == pytest.approx(values[2])

    def test_failed_scenario_disables_weighting(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "scenarios": [
                {"name": "broken", "probability": 0.5, "overrides": {"growth_rate": 0.2}},
                {"name": "base", "probability": 0.5},
            ],
        }
        data = post(client, "/scenario-analysis", payload).json()
        assert data["scenarios"][0]["error"]["code"] == "INVALID_INPUT"
        assert data["probability_weighted_output"] is None

    def test_partial_probabilities_are_rejected(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "scenarios": [{"name": "a", "probability": 1.0}, {"name": "b"}],
        }
        assert post(client, "/scenario-analysis", payload).status_code == 422

    def test_probabilities_must_sum_to_one(self, client: TestClient) -> None:
        payload = {
            "model": "valuation/gordon-growth",
            "output": "value",
            "base_inputs": GORDON,
            "scenarios": [{"name": "a", "probability": 0.5}, {"name": "b", "probability": 0.3}],
        }
        response = post(client, "/scenario-analysis", payload)
        assert response.status_code == 400


class TestStressTest:
    def test_worst_scenario(self, client: TestClient) -> None:
        payload = {
            "positions": [
                {"name": "equities", "exposure": 600000, "sensitivities": {"equity": 1.1}},
                {"name": "gold", "exposure": 100000},
            ],
            "scenarios": [
                {"name": "crash", "shocks": {"equity": -0.3, "gold": 0.08}},
                {"name": "rally", "shocks": {"equity": 0.1}},
            ],
            "currency": "USD",
        }
        data = post(client, "/stress-test", payload).json()
        assert data["worst_scenario"] == "crash"
        assert data["worst_pnl"] == pytest.approx(-190_000)
        assert data["scenarios"][1]["total_pnl"] == pytest.approx(66_000)
        assert data["currency"] == "USD"

    def test_duplicate_names_are_rejected(self, client: TestClient) -> None:
        payload = {
            "positions": [{"name": "a", "exposure": 1}, {"name": "a", "exposure": 2}],
            "scenarios": [{"name": "s", "shocks": {"a": 0.1}}],
        }
        assert post(client, "/stress-test", payload).status_code == 422


class TestMonteCarlo:
    def test_documented_example_is_reproducible(self, client: TestClient) -> None:
        first = post(client, "/monte-carlo", MONTE_CARLO).json()
        second = post(client, "/monte-carlo", MONTE_CARLO).json()
        assert first == second
        assert first["seed_used"] == 42

    def test_statistics_are_consistent_with_theory(self, client: TestClient) -> None:
        data = post(client, "/monte-carlo", MONTE_CARLO).json()

        assert data["horizon_years"] == 1.0
        assert data["theoretical_mean_final_value"] == pytest.approx(100000 * math.exp(0.10))
        assert data["final_value"]["mean"] == pytest.approx(
            data["theoretical_mean_final_value"], rel=0.01
        )
        assert data["probability_of_loss"] == pytest.approx(0.3446, abs=0.02)
        assert data["value_at_risk"]["decimal"] == pytest.approx(
            1 - math.exp(0.08 - 1.6449 * 0.2), abs=0.02
        )
        assert data["expected_shortfall"]["amount"] >= data["value_at_risk"]["amount"]
        ranks = [item["percentile"] for item in data["final_value"]["percentiles"]]
        assert ranks == [5, 25, 50, 75, 95]
        assert all(item["value"] <= 0 for item in data["max_drawdown"]["percentiles"])
        assert data["sample_paths"] == []

    def test_without_seed_returns_the_generated_one(self, client: TestClient) -> None:
        payload = {**MONTE_CARLO, "simulations": 200, "seed": None, "sample_paths": 2}
        data = post(client, "/monte-carlo", payload).json()
        replay = post(client, "/monte-carlo", {**payload, "seed": data["seed_used"]}).json()
        assert replay == data
        assert len(data["sample_paths"]) == 2 and len(data["sample_paths"][0]) == 253

    def test_cell_limit_uses_configuration(self, make_client: Any) -> None:
        limited = make_client(max_monte_carlo_cells=1000)
        response = limited.post(BASE + "/monte-carlo", json=MONTE_CARLO)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "LIMIT_EXCEEDED"

    @pytest.mark.parametrize(
        "change",
        [{"volatility": -0.2}, {"simulations": 0}, {"initial_value": 0}, {"confidence": 1}],
    )
    def test_invalid_parameters(self, client: TestClient, change: dict[str, Any]) -> None:
        assert post(client, "/monte-carlo", {**MONTE_CARLO, **change}).status_code == 422
