"""Request → response tests for structured valuation endpoints (PV, DCF, multi-stage DDM, WACC)."""

from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/valuation"
CASH_FLOWS = [100, 110, 121]
PV_CASH_FLOWS = 3 * 100 / 1.1
TV_GORDON = 121 * 1.02 / 0.08
PV_TV_GORDON = TV_GORDON / 1.331
EV_GORDON = PV_CASH_FLOWS + PV_TV_GORDON


def post(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(BASE + path, json=payload)


class TestPresentValue:
    def test_end_of_period(self, client: TestClient) -> None:
        body = post(client, "/present-value", {"cash_flows": CASH_FLOWS, "discount_rate": 0.1})
        assert body.status_code == 200
        data = body.json()
        assert data["present_value"] == pytest.approx(PV_CASH_FLOWS)
        assert [item["period"] for item in data["discounted_cash_flows"]] == [1, 2, 3]

    def test_custom_fractional_timing_edge(self, client: TestClient) -> None:
        data = post(
            client,
            "/present-value",
            {"cash_flows": [1000], "discount_rate": 0.08, "periods": [2.5]},
        ).json()
        assert data["present_value"] == pytest.approx(1000 / 1.08**2.5)

    def test_mid_year(self, client: TestClient) -> None:
        data = post(
            client,
            "/present-value",
            {"cash_flows": [100], "discount_rate": 0.1, "mid_year_convention": True},
        ).json()
        assert data["present_value"] == pytest.approx(100 / 1.1**0.5)

    @pytest.mark.parametrize(
        "payload",
        [
            {"cash_flows": [], "discount_rate": 0.1},
            {"cash_flows": [1, 2], "discount_rate": 0.1, "periods": [1]},
            {"cash_flows": [1], "discount_rate": 0.1, "periods": [1], "mid_year_convention": True},
            {"cash_flows": [1], "discount_rate": 0.1, "periods": [-1]},
        ],
    )
    def test_invalid_timing(self, client: TestClient, payload: dict[str, Any]) -> None:
        assert post(client, "/present-value", payload).status_code == 422


class TestFcffDcf:
    PAYLOAD: ClassVar[dict[str, Any]] = {
        "cash_flows": CASH_FLOWS,
        "discount_rate": 0.10,
        "terminal": {"method": "perpetuity_growth", "growth_rate": 0.02},
        "net_debt": 300,
        "shares_outstanding": 100,
        "share_price": 9,
        "currency": "BRL",
    }

    def test_perpetuity_growth_known_values(self, client: TestClient) -> None:
        response = post(client, "/dcf/fcff", self.PAYLOAD)
        assert response.status_code == 200
        data = response.json()

        equity = EV_GORDON - 300
        assert data["metric"] == "DCF (FCFF)"
        assert data["enterprise_value"] == pytest.approx(EV_GORDON)
        assert data["terminal_value"] == pytest.approx(TV_GORDON)
        assert data["present_value_of_terminal_value"] == pytest.approx(PV_TV_GORDON)
        assert data["terminal_value_percentage"] == pytest.approx(PV_TV_GORDON / EV_GORDON)
        assert data["equity_value"] == pytest.approx(equity)
        assert data["value_per_share"] == pytest.approx(equity / 100)
        assert data["margin_of_safety"] == pytest.approx((equity / 100 - 9) / (equity / 100))
        assert data["currency"] == "BRL"
        assert len(data["discounted_cash_flows"]) == 3

    def test_first_keys_follow_the_documented_contract(self, client: TestClient) -> None:
        keys = list(post(client, "/dcf/fcff", self.PAYLOAD).json())
        assert keys[:4] == ["metric", "enterprise_value", "equity_value", "terminal_value"]

    def test_exit_multiple_with_mid_year(self, client: TestClient) -> None:
        payload = {
            "cash_flows": CASH_FLOWS,
            "discount_rate": 0.10,
            "terminal": {"method": "exit_multiple", "terminal_metric": 250, "multiple": 8},
            "mid_year_convention": True,
            "net_debt": 300,
            "minority_interest": 50,
            "non_operating_assets": 20,
        }
        data = post(client, "/dcf/fcff", payload).json()

        pv_cf = 100 / 1.1**0.5 + 110 / 1.1**1.5 + 121 / 1.1**2.5
        ev = pv_cf + 2000 / 1.331
        assert data["enterprise_value"] == pytest.approx(ev)
        assert data["equity_value"] == pytest.approx(ev - 300 - 50 + 20)
        assert data["value_per_share"] is None
        assert data["margin_of_safety"] is None

    def test_negative_equity_edge_has_no_margin_of_safety(self, client: TestClient) -> None:
        data = post(client, "/dcf/fcff", {**self.PAYLOAD, "net_debt": 10_000}).json()
        assert data["value_per_share"] < 0
        assert data["margin_of_safety"] is None

    def test_growth_not_below_discount_rate_is_invalid(self, client: TestClient) -> None:
        payload = {**self.PAYLOAD, "terminal": {"method": "perpetuity_growth", "growth_rate": 0.1}}
        response = post(client, "/dcf/fcff", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.parametrize(
        "change",
        [
            {"share_price": 9, "shares_outstanding": None},
            {"terminal": {"method": "exit_multiple", "multiple": 8}},
            {"terminal": {"method": "perpetuity_growth", "growth_rate": 0.02, "extra": 1}},
            {"net_debt": None},
            {"cash_flows": []},
        ],
    )
    def test_schema_violations(self, client: TestClient, change: dict[str, Any]) -> None:
        payload = {**self.PAYLOAD, **change}
        payload = {key: value for key, value in payload.items() if value is not None}
        assert post(client, "/dcf/fcff", payload).status_code == 422


class TestFcfeDcf:
    def test_known_values(self, client: TestClient) -> None:
        payload = {
            "cash_flows": [80, 88, 96.8],
            "cost_of_equity": 0.12,
            "terminal": {"method": "perpetuity_growth", "growth_rate": 0.03},
            "shares_outstanding": 100,
            "share_price": 8,
        }
        data = post(client, "/dcf/fcfe", payload).json()

        pv_cf = 80 / 1.12 + 88 / 1.12**2 + 96.8 / 1.12**3
        terminal = 96.8 * 1.03 / 0.09
        equity = pv_cf + terminal / 1.12**3
        assert data["metric"] == "DCF (FCFE)"
        assert "enterprise_value" not in data
        assert data["terminal_value"] == pytest.approx(terminal)
        assert data["equity_value"] == pytest.approx(equity)
        assert data["value_per_share"] == pytest.approx(equity / 100)

    def test_rejects_net_debt_field(self, client: TestClient) -> None:
        payload = {
            "cash_flows": [80],
            "cost_of_equity": 0.12,
            "terminal": {"method": "exit_multiple", "terminal_metric": 10, "multiple": 5},
            "net_debt": 100,
        }
        assert post(client, "/dcf/fcfe", payload).status_code == 422


class TestMultiStageDdm:
    TWO_STAGE: ClassVar[dict[str, Any]] = {
        "current_dividend": 1,
        "high_growth_rate": 0.10,
        "high_growth_years": 2,
        "stable_growth_rate": 0.03,
        "cost_of_equity": 0.10,
    }

    def test_two_stage_known_value(self, client: TestClient) -> None:
        data = post(client, "/ddm/two-stage", self.TWO_STAGE).json()

        assert data["metric"] == "Two-Stage DDM"
        assert data["value"] == pytest.approx(2 + 1.03 / 0.07)
        assert [p["stage"] for p in data["projections"]] == ["high_growth", "high_growth"]

    def test_two_stage_with_stable_cost_of_equity(self, client: TestClient) -> None:
        data = post(
            client, "/ddm/two-stage", {**self.TWO_STAGE, "stable_cost_of_equity": 0.08}
        ).json()
        assert data["value"] == pytest.approx(2 + 1.03 / 0.05)

    def test_two_stage_invalid_stable_growth(self, client: TestClient) -> None:
        response = post(client, "/ddm/two-stage", {**self.TWO_STAGE, "stable_growth_rate": 0.10})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"

    def test_three_stage_known_value(self, client: TestClient) -> None:
        payload = {**self.TWO_STAGE, "high_growth_years": 1, "transition_years": 2}
        payload["stable_growth_rate"] = 0.04
        data = post(client, "/ddm/three-stage", payload).json()

        d1, d2, d3 = 1.1, 1.1 * 1.07, 1.1 * 1.07 * 1.04
        expected = d1 / 1.1 + d2 / 1.1**2 + d3 / 1.1**3 + (d3 * 1.04 / 0.06) / 1.1**3
        assert data["metric"] == "Three-Stage DDM"
        assert data["value"] == pytest.approx(expected)
        assert [p["growth_rate"] for p in data["projections"]] == pytest.approx([0.1, 0.07, 0.04])

    @pytest.mark.parametrize("years", [0, 101])
    def test_three_stage_year_bounds(self, client: TestClient, years: int) -> None:
        payload = {**self.TWO_STAGE, "transition_years": years}
        assert post(client, "/ddm/three-stage", payload).status_code == 422


class TestWacc:
    PAYLOAD: ClassVar[dict[str, Any]] = {
        "equity_value": 600,
        "debt_value": 400,
        "cost_of_equity": 0.12,
        "pre_tax_cost_of_debt": 0.08,
        "tax_rate": 0.34,
    }

    def test_known_value_and_components(self, client: TestClient) -> None:
        data = post(client, "/wacc", self.PAYLOAD).json()

        assert data["metric"] == "WACC"
        assert data["unit"] == "decimal"
        assert data["value"] == pytest.approx(0.09312)
        components = {c["metric"]: c["value"] for c in data["components"]}
        assert components["Equity Weight"] == pytest.approx(0.6)
        assert components["Debt Weight"] == pytest.approx(0.4)
        assert components["After-tax Cost of Debt"] == pytest.approx(0.0528)

    def test_all_equity_edge(self, client: TestClient) -> None:
        data = post(client, "/wacc", {**self.PAYLOAD, "debt_value": 0}).json()
        assert data["value"] == pytest.approx(0.12)

    def test_zero_capital_is_division_by_zero(self, client: TestClient) -> None:
        response = post(client, "/wacc", {**self.PAYLOAD, "equity_value": 0, "debt_value": 0})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "DIVISION_BY_ZERO"

    def test_negative_market_value_is_rejected(self, client: TestClient) -> None:
        assert post(client, "/wacc", {**self.PAYLOAD, "debt_value": -1}).status_code == 422
