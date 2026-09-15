"""Normal / edge / invalid cases for every single-value valuation endpoint."""

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.valuation import METRIC_ENDPOINTS

BASE = "/api/v1/valuation"


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


V422 = (422, "VALIDATION_ERROR")
INVALID = (400, "INVALID_INPUT")
DIV0 = (400, "DIVISION_BY_ZERO")


def bad(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, *expected


CASES: dict[str, Case] = {
    "/future-value": Case(
        ({"present_value": 1000, "rate": 0.05, "periods": 10}, 1000 * 1.05**10),
        ({"present_value": 1000, "rate": 0.05, "periods": 0}, 1000.0),
        bad({"present_value": 1000, "rate": -1, "periods": 10}, V422),
    ),
    "/terminal-value/perpetuity-growth": Case(
        ({"final_cash_flow": 121, "discount_rate": 0.10, "growth_rate": 0.02}, 1542.75),
        ({"final_cash_flow": 121, "discount_rate": 0.10, "growth_rate": 0}, 1210.0),
        bad({"final_cash_flow": 121, "discount_rate": 0.02, "growth_rate": 0.02}, INVALID),
    ),
    "/terminal-value/exit-multiple": Case(
        ({"terminal_metric": 250, "multiple": 8}, 2000.0),
        ({"terminal_metric": -50, "multiple": 8}, -400.0),
        bad({"terminal_metric": 250}, V422),
    ),
    "/enterprise-value": Case(
        (
            {"present_value_of_cash_flows": 272.73, "present_value_of_terminal_value": 1159.09},
            1431.82,
        ),
        ({"present_value_of_cash_flows": -100, "present_value_of_terminal_value": 50}, -50.0),
        bad({"present_value_of_cash_flows": 272.73}, V422),
    ),
    "/equity-value": Case(
        (
            {
                "enterprise_value": 1431.82,
                "net_debt": 300,
                "minority_interest": 50,
                "non_operating_assets": 20,
            },
            1101.82,
        ),
        ({"enterprise_value": 1431.82, "net_debt": -200}, 1631.82),
        bad({"enterprise_value": 1431.82, "net_debt": 300, "minority_interest": -1}, V422),
    ),
    "/value-per-share": Case(
        ({"equity_value": 1101.82, "shares_outstanding": 100}, 11.0182),
        ({"equity_value": -500, "shares_outstanding": 100}, -5.0),
        bad({"equity_value": 1101.82, "shares_outstanding": 0}, V422),
    ),
    "/margin-of-safety": Case(
        ({"intrinsic_value": 50, "market_price": 35}, 0.3),
        ({"intrinsic_value": 50, "market_price": 60}, -0.2),
        bad({"intrinsic_value": -10, "market_price": 35}, INVALID),
    ),
    "/ddm": Case(
        (
            {"dividends": [2, 2.1, 2.2], "cost_of_equity": 0.10, "terminal_price": 40},
            2 / 1.1 + 2.1 / 1.1**2 + 2.2 / 1.1**3 + 40 / 1.1**3,
        ),
        ({"dividends": [0, 0], "cost_of_equity": 0.10}, 0.0),
        bad({"dividends": [2], "cost_of_equity": -1}, V422),
    ),
    "/gordon-growth": Case(
        ({"current_dividend": 2, "cost_of_equity": 0.10, "growth_rate": 0.05}, 42.0),
        ({"next_dividend": 2, "cost_of_equity": 0.10, "growth_rate": -0.02}, 2 / 0.12),
        bad({"current_dividend": 2, "cost_of_equity": 0.05, "growth_rate": 0.05}, INVALID),
    ),
    "/capm": Case(
        ({"risk_free_rate": 0.04, "beta": 1.2, "market_risk_premium": 0.055}, 0.106),
        ({"risk_free_rate": 0.04, "beta": 0, "expected_market_return": 0.10}, 0.04),
        bad(
            {
                "risk_free_rate": 0.04,
                "beta": 1.2,
                "market_risk_premium": 0.055,
                "expected_market_return": 0.10,
            },
            V422,
        ),
    ),
    "/levered-beta": Case(
        ({"unlevered_beta": 0.8, "tax_rate": 0.34, "debt_to_equity": 0.5}, 1.064),
        ({"unlevered_beta": 0.8, "tax_rate": 0.34, "debt_to_equity": 0}, 0.8),
        bad({"unlevered_beta": 0.8, "tax_rate": 0.34, "debt_to_equity": -0.5}, V422),
    ),
    "/unlevered-beta": Case(
        ({"levered_beta": 1.064, "tax_rate": 0.34, "debt_to_equity": 0.5}, 0.8),
        ({"levered_beta": 1.064, "tax_rate": 1, "debt_to_equity": 0.5}, 1.064),
        bad({"levered_beta": 1.064, "tax_rate": 1.5, "debt_to_equity": 0.5}, V422),
    ),
    "/cost-of-equity": Case(
        (
            {
                "risk_free_rate": 0.04,
                "beta": 1.2,
                "market_risk_premium": 0.055,
                "country_risk_premium": 0.02,
                "size_premium": 0.01,
            },
            0.136,
        ),
        ({"risk_free_rate": 0.04, "beta": 1.2, "expected_market_return": 0.10}, 0.112),
        bad({"risk_free_rate": 0.04, "beta": 1.2}, V422),
    ),
    "/cost-of-debt": Case(
        ({"risk_free_rate": 0.04, "credit_spread": 0.02}, 0.06),
        ({"method": "interest_over_debt", "interest_expense": 45, "total_debt": 500}, 0.09),
        bad({"method": "interest_over_debt", "interest_expense": 45, "total_debt": 0}, DIV0),
    ),
    "/after-tax-cost-of-debt": Case(
        ({"pre_tax_cost_of_debt": 0.08, "tax_rate": 0.34}, 0.0528),
        ({"pre_tax_cost_of_debt": 0.08, "tax_rate": 0}, 0.08),
        bad({"pre_tax_cost_of_debt": 0.08, "tax_rate": -0.1}, V422),
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
    assert body["value"] == pytest.approx(expected, rel=1e-12, abs=1e-12)


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


@pytest.mark.parametrize("path", PATHS)
def test_empty_body_is_rejected(client: TestClient, path: str) -> None:
    assert client.post(BASE + path, json={}).status_code == 422


def test_gordon_rejects_both_dividend_inputs(client: TestClient) -> None:
    response = client.post(
        BASE + "/gordon-growth",
        json={"current_dividend": 2, "next_dividend": 2.1, "cost_of_equity": 0.1, "growth_rate": 0},
    )
    assert response.status_code == 422
    assert "exactly one" in response.json()["error"]["details"][0]["message"]


def test_cost_of_debt_method_requires_its_fields(client: TestClient) -> None:
    response = client.post(BASE + "/cost-of-debt", json={"method": "interest_over_debt"})
    assert response.status_code == 422
    assert "interest_expense" in response.json()["error"]["details"][0]["message"]


def test_amount_results_echo_currency(client: TestClient) -> None:
    body = client.post(
        BASE + "/value-per-share",
        json={"equity_value": 1000, "shares_outstanding": 10, "currency": "USD"},
    ).json()
    assert body["currency"] == "USD"
