"""Request → endpoint → response tests for every single-value fundamentals endpoint.

Each endpoint has a normal case, an edge case and an invalid case with independently
computed expected values. A guard test fails if a new endpoint is registered without cases.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.fundamentals import METRIC_ENDPOINTS

BASE = "/api/v1/fundamentals"


@dataclass(frozen=True)
class Case:
    normal: tuple[dict[str, Any], float]
    edge: tuple[dict[str, Any], float]
    invalid: tuple[dict[str, Any], int, str]


DIV0 = (400, "DIVISION_BY_ZERO")
VALIDATION = (422, "VALIDATION_ERROR")
INVALID = (400, "INVALID_INPUT")


def invalid(payload: dict[str, Any], expected: tuple[int, str]) -> tuple[dict[str, Any], int, str]:
    return payload, expected[0], expected[1]


CASES: dict[str, Case] = {
    # --- Multiples ---
    "/pe-ratio": Case(
        ({"share_price": 35.5, "earnings_per_share": 4.2}, 35.5 / 4.2),
        ({"share_price": 30, "earnings_per_share": -2}, -15.0),
        invalid({"share_price": 35.5, "earnings_per_share": 0}, DIV0),
    ),
    "/pb-ratio": Case(
        ({"share_price": 20, "book_value_per_share": 16}, 1.25),
        ({"share_price": 20, "book_value_per_share": -4}, -5.0),
        invalid({"share_price": 0, "book_value_per_share": 16}, VALIDATION),
    ),
    "/ps-ratio": Case(
        ({"market_capitalization": 5e9, "revenue": 2e9}, 2.5),
        ({"market_capitalization": 5e9, "revenue": 1}, 5e9),
        invalid({"market_capitalization": 5e9, "revenue": 0}, DIV0),
    ),
    "/ev-to-ebitda": Case(
        ({"enterprise_value": 12e9, "ebitda": 1.5e9}, 8.0),
        ({"enterprise_value": 12e9, "ebitda": -1e9}, -12.0),
        invalid({"enterprise_value": 12e9, "ebitda": 0}, DIV0),
    ),
    "/ev-to-ebit": Case(
        ({"enterprise_value": 12e9, "ebit": 1e9}, 12.0),
        ({"enterprise_value": -1e9, "ebit": 5e8}, -2.0),
        invalid({"enterprise_value": 12e9, "ebit": 0}, DIV0),
    ),
    "/ev-to-revenue": Case(
        ({"enterprise_value": 12e9, "revenue": 4e9}, 3.0),
        ({"enterprise_value": 0, "revenue": 4e9}, 0.0),
        invalid({"enterprise_value": 12e9, "revenue": 0}, DIV0),
    ),
    "/ev-to-fcf": Case(
        ({"enterprise_value": 12e9, "free_cash_flow": 8e8}, 15.0),
        ({"enterprise_value": 12e9, "free_cash_flow": -8e8}, -15.0),
        invalid({"enterprise_value": 12e9, "free_cash_flow": 0}, DIV0),
    ),
    "/earnings-yield": Case(
        ({"earnings_per_share": 4.2, "share_price": 35.5}, 4.2 / 35.5),
        ({"method": "ebit_to_enterprise_value", "ebit": 1e9, "enterprise_value": 12e9}, 1 / 12),
        invalid({"method": "ebit_to_enterprise_value", "earnings_per_share": 4.2}, VALIDATION),
    ),
    "/fcf-yield": Case(
        ({"free_cash_flow": 4e8, "market_capitalization": 5e9}, 0.08),
        ({"free_cash_flow": -4e8, "market_capitalization": 5e9}, -0.08),
        invalid({"free_cash_flow": 4e8, "market_capitalization": 0}, VALIDATION),
    ),
    "/ebitda-yield": Case(
        ({"ebitda": 1.5e9, "enterprise_value": 12e9}, 0.125),
        ({"ebitda": 0, "enterprise_value": 12e9}, 0.0),
        invalid({"ebitda": 1.5e9, "enterprise_value": 0}, DIV0),
    ),
    "/peg-ratio": Case(
        ({"pe_ratio": 15, "earnings_growth_rate": 0.10}, 1.5),
        ({"pe_ratio": 15, "earnings_growth_rate": -0.05}, -3.0),
        invalid({"pe_ratio": 15, "earnings_growth_rate": 0}, DIV0),
    ),
    # --- Profitability ---
    "/roe": Case(
        ({"net_income": 180, "shareholders_equity": 1000}, 0.18),
        ({"net_income": 180, "shareholders_equity": {"beginning": 900, "ending": 1100}}, 0.18),
        invalid({"net_income": 180, "shareholders_equity": 0}, DIV0),
    ),
    "/roa": Case(
        ({"net_income": 180, "total_assets": 2400}, 0.075),
        ({"net_income": -60, "total_assets": {"beginning": 2200, "ending": 2600}}, -0.025),
        invalid({"net_income": 180, "total_assets": 0}, DIV0),
    ),
    "/roic": Case(
        ({"ebit": 300, "tax_rate": 0.34, "invested_capital": 1200}, 0.165),
        (
            {
                "ebit": 300,
                "tax_rate": 0.34,
                "total_debt": 500,
                "shareholders_equity": 1000,
                "cash_and_equivalents": 300,
            },
            0.165,
        ),
        invalid({"ebit": 300, "tax_rate": 1.2, "invested_capital": 1200}, VALIDATION),
    ),
    "/roce": Case(
        ({"ebit": 300, "total_assets": 2400, "current_liabilities": 400}, 0.15),
        ({"ebit": -100, "total_assets": 2400, "current_liabilities": 400}, -0.05),
        invalid({"ebit": 300, "total_assets": 400, "current_liabilities": 400}, DIV0),
    ),
    "/gross-margin": Case(
        ({"gross_profit": 400, "revenue": 1000}, 0.4),
        ({"gross_profit": -50, "revenue": 1000}, -0.05),
        invalid({"gross_profit": 400, "revenue": 0}, DIV0),
    ),
    "/ebitda-margin": Case(
        ({"ebitda": 250, "revenue": 1000}, 0.25),
        ({"ebitda": 1000, "revenue": 1000}, 1.0),
        invalid({"ebitda": 250, "revenue": 0}, DIV0),
    ),
    "/ebit-margin": Case(
        ({"ebit": 180, "revenue": 1000}, 0.18),
        ({"ebit": 0, "revenue": 1000}, 0.0),
        invalid({"ebit": 180}, VALIDATION),
    ),
    "/net-margin": Case(
        ({"net_income": 120, "revenue": 1000}, 0.12),
        ({"net_income": -120, "revenue": 1000}, -0.12),
        invalid({"net_income": 120, "revenue": 0}, DIV0),
    ),
    "/fcf-margin": Case(
        ({"free_cash_flow": 90, "revenue": 1000}, 0.09),
        ({"free_cash_flow": -90, "revenue": 1000}, -0.09),
        invalid({"free_cash_flow": 90, "revenue": 0}, DIV0),
    ),
    "/asset-turnover": Case(
        ({"revenue": 1000, "total_assets": 2000}, 0.5),
        ({"revenue": 1000, "total_assets": {"beginning": 1800, "ending": 2200}}, 0.5),
        invalid({"revenue": 1000, "total_assets": {"beginning": 0, "ending": 0}}, DIV0),
    ),
    # --- Growth ---
    "/revenue-growth": Case(
        ({"current_value": 1100, "previous_value": 1000}, 0.1),
        ({"current_value": -50, "previous_value": -100}, 0.5),
        invalid({"current_value": 1100, "previous_value": 0}, DIV0),
    ),
    "/ebitda-growth": Case(
        ({"current_value": 270, "previous_value": 250}, 0.08),
        ({"current_value": 50, "previous_value": -100}, 1.5),
        invalid({"current_value": 270, "previous_value": 0}, DIV0),
    ),
    "/ebit-growth": Case(
        ({"current_value": 198, "previous_value": 180}, 0.1),
        ({"current_value": 180, "previous_value": 180}, 0.0),
        invalid({"current_value": 198}, VALIDATION),
    ),
    "/net-income-growth": Case(
        ({"current_value": 150, "previous_value": 120}, 0.25),
        ({"current_value": -120, "previous_value": 120}, -2.0),
        invalid({"current_value": 150, "previous_value": 0}, DIV0),
    ),
    "/eps-growth": Case(
        ({"current_value": 4.62, "previous_value": 4.20}, 0.1),
        ({"current_value": 0, "previous_value": 4.20}, -1.0),
        invalid({"current_value": 4.62, "previous_value": 0}, DIV0),
    ),
    "/fcf-growth": Case(
        ({"current_value": 81, "previous_value": 90}, -0.1),
        ({"current_value": -45, "previous_value": -90}, 0.5),
        invalid({"current_value": 81, "previous_value": 0}, DIV0),
    ),
    "/cagr": Case(
        ({"beginning_value": 100, "ending_value": 200, "years": 5}, 2 ** (1 / 5) - 1),
        ({"beginning_value": 100, "ending_value": 110, "years": 0.5}, 0.21),
        invalid({"beginning_value": 0, "ending_value": 200, "years": 5}, INVALID),
    ),
    "/sustainable-growth-rate": Case(
        ({"return_on_equity": 0.18, "retention_ratio": 0.6}, 0.108),
        ({"return_on_equity": 0.18, "retention_ratio": 0}, 0.0),
        invalid({"return_on_equity": 0.18}, VALIDATION),
    ),
    "/retention-ratio": Case(
        ({"net_income": 200, "dividends_paid": 50}, 0.75),
        ({"net_income": 200, "dividends_paid": 0}, 1.0),
        invalid({"net_income": 0, "dividends_paid": 50}, DIV0),
    ),
    "/reinvestment-rate": Case(
        (
            {
                "capital_expenditures": 150,
                "depreciation_amortization": 50,
                "change_in_working_capital": 20,
                "ebit": 300,
                "tax_rate": 0.34,
            },
            120 / 198,
        ),
        (
            {
                "capital_expenditures": 50,
                "depreciation_amortization": 50,
                "change_in_working_capital": 0,
                "ebit": 300,
                "tax_rate": 0,
            },
            0.0,
        ),
        invalid(
            {
                "capital_expenditures": 150,
                "depreciation_amortization": 50,
                "change_in_working_capital": 20,
                "ebit": 300,
                "tax_rate": 1,
            },
            DIV0,
        ),
    ),
    # --- Debt ---
    "/gross-debt": Case(
        ({"short_term_debt": 200, "long_term_debt": 800, "lease_liabilities": 100}, 1100.0),
        ({"short_term_debt": 200, "long_term_debt": 800}, 1000.0),
        invalid({"short_term_debt": -1, "long_term_debt": 800}, VALIDATION),
    ),
    "/net-debt": Case(
        (
            {"gross_debt": 1100, "cash_and_equivalents": 300, "short_term_investments": 100},
            700.0,
        ),
        ({"gross_debt": 100, "cash_and_equivalents": 300}, -200.0),
        invalid({"gross_debt": 1100, "cash_and_equivalents": -1}, VALIDATION),
    ),
    "/net-debt-to-ebitda": Case(
        ({"net_debt": 700, "ebitda": 350}, 2.0),
        ({"net_debt": -200, "ebitda": 350}, -200 / 350),
        invalid({"net_debt": 700, "ebitda": 0}, DIV0),
    ),
    "/debt-to-equity": Case(
        ({"gross_debt": 1100, "shareholders_equity": 2200}, 0.5),
        ({"gross_debt": 1100, "shareholders_equity": -1100}, -1.0),
        invalid({"gross_debt": 1100, "shareholders_equity": 0}, DIV0),
    ),
    "/debt-to-capital": Case(
        ({"gross_debt": 1100, "shareholders_equity": 2200}, 1 / 3),
        ({"gross_debt": 0, "shareholders_equity": 2200}, 0.0),
        invalid({"gross_debt": 0, "shareholders_equity": 0}, DIV0),
    ),
    "/interest-coverage": Case(
        ({"ebit": 300, "interest_expense": 60}, 5.0),
        ({"ebit": -30, "interest_expense": 60}, -0.5),
        invalid({"ebit": 300, "interest_expense": 0}, DIV0),
    ),
    "/debt-to-fcf": Case(
        ({"gross_debt": 1100, "free_cash_flow": 220}, 5.0),
        ({"gross_debt": 1100, "free_cash_flow": -220}, -5.0),
        invalid({"gross_debt": 1100, "free_cash_flow": 0}, DIV0),
    ),
    # --- Liquidity ---
    "/current-ratio": Case(
        ({"current_assets": 1500, "current_liabilities": 1000}, 1.5),
        ({"current_assets": 0, "current_liabilities": 1000}, 0.0),
        invalid({"current_assets": 1500, "current_liabilities": 0}, DIV0),
    ),
    "/quick-ratio": Case(
        ({"current_assets": 1500, "inventories": 500, "current_liabilities": 1000}, 1.0),
        ({"current_assets": 1500, "inventories": 1500, "current_liabilities": 1000}, 0.0),
        invalid({"current_assets": 400, "inventories": 500, "current_liabilities": 1000}, INVALID),
    ),
    "/cash-ratio": Case(
        (
            {
                "cash_and_equivalents": 300,
                "short_term_investments": 100,
                "current_liabilities": 1000,
            },
            0.4,
        ),
        ({"cash_and_equivalents": 300, "current_liabilities": 1000}, 0.3),
        invalid({"cash_and_equivalents": 300, "current_liabilities": 0}, DIV0),
    ),
    "/general-liquidity-ratio": Case(
        (
            {
                "current_assets": 1500,
                "long_term_receivables": 500,
                "current_liabilities": 1000,
                "non_current_liabilities": 1500,
            },
            0.8,
        ),
        (
            {
                "current_assets": 1500,
                "long_term_receivables": 0,
                "current_liabilities": 1000,
                "non_current_liabilities": 0,
            },
            1.5,
        ),
        invalid(
            {
                "current_assets": 1500,
                "long_term_receivables": 500,
                "current_liabilities": 0,
                "non_current_liabilities": 0,
            },
            DIV0,
        ),
    ),
    # --- Cash flow ---
    "/free-cash-flow": Case(
        ({"operating_cash_flow": 500, "capital_expenditures": 200}, 300.0),
        ({"operating_cash_flow": 100, "capital_expenditures": 200}, -100.0),
        invalid({"operating_cash_flow": 500, "capital_expenditures": -200}, VALIDATION),
    ),
    "/fcff": Case(
        (
            {
                "ebit": 300,
                "tax_rate": 0.34,
                "depreciation_amortization": 50,
                "capital_expenditures": 150,
                "change_in_working_capital": 20,
            },
            78.0,
        ),
        (
            {
                "ebit": 300,
                "tax_rate": 0,
                "depreciation_amortization": 50,
                "capital_expenditures": 150,
                "change_in_working_capital": -20,
            },
            220.0,
        ),
        invalid(
            {
                "ebit": 300,
                "tax_rate": -0.1,
                "depreciation_amortization": 50,
                "capital_expenditures": 150,
                "change_in_working_capital": 20,
            },
            VALIDATION,
        ),
    ),
    "/fcfe": Case(
        (
            {
                "free_cash_flow_to_firm": 78,
                "interest_expense": 40,
                "tax_rate": 0.34,
                "net_borrowing": 30,
            },
            81.6,
        ),
        (
            {
                "free_cash_flow_to_firm": 78,
                "interest_expense": 40,
                "tax_rate": 0.34,
                "net_borrowing": -50,
            },
            1.6,
        ),
        invalid(
            {
                "free_cash_flow_to_firm": 78,
                "interest_expense": -40,
                "tax_rate": 0.34,
                "net_borrowing": 30,
            },
            VALIDATION,
        ),
    ),
    "/fcf-conversion": Case(
        ({"free_cash_flow": 90, "net_income": 120}, 0.75),
        ({"free_cash_flow": 90, "net_income": -120}, -0.75),
        invalid({"free_cash_flow": 90, "net_income": 0}, DIV0),
    ),
    "/cash-conversion-ratio": Case(
        ({"operating_cash_flow": 150, "net_income": 120}, 1.25),
        ({"operating_cash_flow": 0, "net_income": 120}, 0.0),
        invalid({"operating_cash_flow": 150, "net_income": 0}, DIV0),
    ),
    "/cfo-margin": Case(
        ({"operating_cash_flow": 150, "revenue": 1000}, 0.15),
        ({"operating_cash_flow": -150, "revenue": 1000}, -0.15),
        invalid({"operating_cash_flow": 150, "revenue": 0}, DIV0),
    ),
    "/capex-to-revenue": Case(
        ({"capital_expenditures": 60, "revenue": 1000}, 0.06),
        ({"capital_expenditures": 0, "revenue": 1000}, 0.0),
        invalid({"capital_expenditures": 60, "revenue": 0}, DIV0),
    ),
    "/capex-to-depreciation": Case(
        ({"capital_expenditures": 60, "depreciation_amortization": 40}, 1.5),
        ({"capital_expenditures": 40, "depreciation_amortization": 40}, 1.0),
        invalid({"capital_expenditures": 60, "depreciation_amortization": 0}, DIV0),
    ),
    "/cash-flow-per-share": Case(
        ({"operating_cash_flow": 150, "shares_outstanding": 50}, 3.0),
        ({"operating_cash_flow": -150, "shares_outstanding": 50}, -3.0),
        invalid({"operating_cash_flow": 150, "shares_outstanding": 0}, VALIDATION),
    ),
    "/owner-earnings": Case(
        (
            {
                "net_income": 120,
                "depreciation_amortization": 40,
                "maintenance_capital_expenditures": 30,
                "change_in_working_capital": 10,
            },
            120.0,
        ),
        (
            {
                "net_income": 120,
                "depreciation_amortization": 40,
                "maintenance_capital_expenditures": 30,
                "change_in_working_capital": -10,
            },
            140.0,
        ),
        invalid(
            {
                "net_income": 120,
                "depreciation_amortization": 40,
                "maintenance_capital_expenditures": -30,
                "change_in_working_capital": 10,
            },
            VALIDATION,
        ),
    ),
    # --- Dividends ---
    "/dividend-yield": Case(
        ({"dividend_per_share": 2.1, "share_price": 35}, 0.06),
        ({"dividend_per_share": 0, "share_price": 35}, 0.0),
        invalid({"dividend_per_share": 2.1, "share_price": 0}, VALIDATION),
    ),
    "/dividend-payout": Case(
        ({"dividends_paid": 60, "net_income": 120}, 0.5),
        ({"dividends_paid": 60, "net_income": -120}, -0.5),
        invalid({"dividends_paid": 60, "net_income": 0}, DIV0),
    ),
    "/dividend-coverage": Case(
        ({"earnings_per_share": 4.2, "dividend_per_share": 2.1}, 2.0),
        ({"earnings_per_share": -4.2, "dividend_per_share": 2.1}, -2.0),
        invalid({"earnings_per_share": 4.2, "dividend_per_share": 0}, DIV0),
    ),
    "/dividend-cagr": Case(
        ({"beginning_dividend": 1.0, "ending_dividend": 1.61051, "years": 5}, 0.1),
        ({"beginning_dividend": 1.0, "ending_dividend": 0.5, "years": 1}, -0.5),
        invalid({"beginning_dividend": 1.0, "ending_dividend": 0, "years": 5}, INVALID),
    ),
    "/dividend-per-share": Case(
        ({"total_dividends": 60_000_000, "shares_outstanding": 50_000_000}, 1.2),
        ({"total_dividends": 0, "shares_outstanding": 50_000_000}, 0.0),
        invalid({"total_dividends": 60_000_000, "shares_outstanding": 0}, VALIDATION),
    ),
    "/yield-on-cost": Case(
        ({"dividend_per_share": 2.1, "average_cost_per_share": 15}, 0.14),
        ({"dividend_per_share": 0, "average_cost_per_share": 15}, 0.0),
        invalid({"dividend_per_share": 2.1, "average_cost_per_share": 0}, VALIDATION),
    ),
}

ENDPOINTS_BY_PATH = {endpoint.path: endpoint for endpoint in METRIC_ENDPOINTS}
PATHS = sorted(ENDPOINTS_BY_PATH)


def test_every_registered_endpoint_has_test_cases() -> None:
    assert set(CASES) == set(ENDPOINTS_BY_PATH)


def _assert_metric(response_json: dict[str, Any], path: str, expected: float) -> None:
    endpoint = ENDPOINTS_BY_PATH[path]
    assert set(response_json) == {"metric", "value", "unit", "currency"}
    assert response_json["metric"] == endpoint.metric
    assert response_json["unit"] == endpoint.unit.value
    assert response_json["value"] == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("path", PATHS)
def test_normal_case(client: TestClient, path: str) -> None:
    payload, expected = CASES[path].normal

    response = client.post(BASE + path, json=payload)

    assert response.status_code == 200, response.text
    _assert_metric(response.json(), path, expected)


@pytest.mark.parametrize("path", PATHS)
def test_edge_case(client: TestClient, path: str) -> None:
    payload, expected = CASES[path].edge

    response = client.post(BASE + path, json=payload)

    assert response.status_code == 200, response.text
    _assert_metric(response.json(), path, expected)


@pytest.mark.parametrize("path", PATHS)
def test_invalid_case(client: TestClient, path: str) -> None:
    payload, status, code = CASES[path].invalid

    response = client.post(BASE + path, json=payload)

    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("path", PATHS)
def test_empty_body_is_rejected(client: TestClient, path: str) -> None:
    response = client.post(BASE + path, json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("path", PATHS)
def test_unknown_field_is_rejected(client: TestClient, path: str) -> None:
    payload = {**CASES[path].normal[0], "unexpected_field": 1}

    response = client.post(BASE + path, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("path", PATHS)
def test_documented_example_matches_live_response(
    client: TestClient, openapi: dict[str, Any], path: str
) -> None:
    operation = openapi["paths"][BASE + path]["post"]
    example_request = operation["requestBody"]["content"]["application/json"]["examples"][
        "example"
    ]["value"]
    example_response = operation["responses"]["200"]["content"]["application/json"]["examples"][
        "example"
    ]["value"]

    live = client.post(BASE + path, json=example_request).json()

    assert live["value"] == example_response["value"]
    assert live["metric"] == example_response["metric"]


@pytest.mark.parametrize("path", PATHS)
def test_openapi_documents_formula_unit_and_errors(openapi: dict[str, Any], path: str) -> None:
    operation = openapi["paths"][BASE + path]["post"]

    assert "**Formula:**" in operation["description"]
    assert "**Unit:**" in operation["description"]
    assert {"200", "400", "422", "500"} <= set(operation["responses"])


def test_currency_is_echoed_only_for_amount_results(client: TestClient) -> None:
    amount = client.post(
        BASE + "/net-debt",
        json={"gross_debt": 1100, "cash_and_equivalents": 300, "currency": "BRL"},
    ).json()
    ratio = client.post(
        BASE + "/pe-ratio",
        json={"share_price": 35.5, "earnings_per_share": 4.2, "currency": "BRL"},
    ).json()

    assert amount["currency"] == "BRL"
    assert ratio["currency"] is None


def test_currency_never_changes_the_math(client: TestClient) -> None:
    payload = {"gross_debt": 1100, "cash_and_equivalents": 300}

    brl = client.post(BASE + "/net-debt", json={**payload, "currency": "BRL"}).json()
    usd = client.post(BASE + "/net-debt", json={**payload, "currency": "USD"}).json()

    assert brl["value"] == usd["value"] == 800.0


def test_invalid_currency_code_is_rejected(client: TestClient) -> None:
    response = client.post(
        BASE + "/net-debt",
        json={"gross_debt": 1100, "cash_and_equivalents": 300, "currency": "real"},
    )

    assert response.status_code == 422


def test_roic_rejects_mixed_invested_capital_sources(client: TestClient) -> None:
    response = client.post(
        BASE + "/roic",
        json={"ebit": 300, "tax_rate": 0.34, "invested_capital": 1200, "total_debt": 500},
    )

    assert response.status_code == 422
    assert "not both" in response.json()["error"]["details"][0]["message"]


def test_roic_requires_all_components_when_invested_capital_is_absent(client: TestClient) -> None:
    response = client.post(BASE + "/roic", json={"ebit": 300, "tax_rate": 0.34, "total_debt": 500})

    assert response.status_code == 422


def test_huge_values_that_overflow_return_non_finite_error(client: TestClient) -> None:
    response = client.post(
        BASE + "/gross-debt", json={"short_term_debt": 1e308, "long_term_debt": 1e308}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "NON_FINITE_RESULT"
