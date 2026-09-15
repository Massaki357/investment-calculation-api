import pytest
from fastapi.testclient import TestClient

URL = "/api/v1/fundamentals/dupont"

THREE_FACTOR = {
    "net_income": 120,
    "revenue": 1000,
    "total_assets": 2000,
    "shareholders_equity": 800,
}
FIVE_FACTOR = {**THREE_FACTOR, "method": "five_factor", "pretax_income": 160, "ebit": 200}


def _components(body: dict) -> dict[str, tuple[float, str]]:
    return {c["metric"]: (c["value"], c["unit"]) for c in body["components"]}


def test_three_factor_is_the_default(client: TestClient) -> None:
    response = client.post(URL, json=THREE_FACTOR)

    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "DuPont Analysis"
    assert body["method"] == "three_factor"
    assert body["return_on_equity"] == pytest.approx(0.15)
    components = _components(body)
    assert components.keys() == {"Net Profit Margin", "Asset Turnover", "Equity Multiplier"}
    assert components["Net Profit Margin"] == (pytest.approx(0.12), "decimal")
    assert components["Asset Turnover"] == (pytest.approx(0.5), "multiple")
    assert components["Equity Multiplier"] == (pytest.approx(2.5), "multiple")


def test_five_factor_known_values(client: TestClient) -> None:
    response = client.post(URL, json=FIVE_FACTOR)

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "five_factor"
    assert body["return_on_equity"] == pytest.approx(0.15)
    components = _components(body)
    assert components["Tax Burden"][0] == pytest.approx(0.75)
    assert components["Interest Burden"][0] == pytest.approx(0.8)
    assert components["Operating Margin"][0] == pytest.approx(0.2)
    assert len(components) == 5


def test_edge_case_average_balances(client: TestClient) -> None:
    payload = {
        **THREE_FACTOR,
        "total_assets": {"beginning": 1800, "ending": 2200},
        "shareholders_equity": {"beginning": 700, "ending": 900},
    }

    body = client.post(URL, json=payload).json()

    assert body["return_on_equity"] == pytest.approx(0.15)


def test_five_factor_requires_extra_fields(client: TestClient) -> None:
    response = client.post(URL, json={**THREE_FACTOR, "method": "five_factor"})

    assert response.status_code == 422
    assert "pretax_income" in response.json()["error"]["details"][0]["message"]


def test_zero_equity_returns_division_by_zero(client: TestClient) -> None:
    response = client.post(URL, json={**THREE_FACTOR, "shareholders_equity": 0})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DIVISION_BY_ZERO"


def test_unknown_method_is_rejected(client: TestClient) -> None:
    response = client.post(URL, json={**THREE_FACTOR, "method": "seven_factor"})

    assert response.status_code == 422
