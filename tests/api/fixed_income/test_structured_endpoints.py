"""Request → response tests for structured fixed income endpoints."""

import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/fixed-income"
SEMI = {"face_value": 1000, "coupon_rate": 0.06, "years_to_maturity": 5, "coupon_frequency": 2}
SEMI_AT_8 = math.fsum(30 / 1.04**k for k in range(1, 11)) + 1000 / 1.04**10


def post(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(BASE + path, json=payload)


def components(body: dict[str, Any]) -> dict[str, float]:
    return {item["metric"]: item["value"] for item in body["components"]}


class TestInterest:
    def test_simple_interest(self, client: TestClient) -> None:
        data = post(
            client, "/simple-interest", {"principal": 1000, "rate": 0.12, "years": 2}
        ).json()
        assert data["interest"] == pytest.approx(240)
        assert data["future_value"] == pytest.approx(1240)

    def test_simple_interest_negative_rate_edge(self, client: TestClient) -> None:
        data = post(
            client, "/simple-interest", {"principal": 1000, "rate": -0.05, "years": 1}
        ).json()
        assert data["interest"] == pytest.approx(-50)

    def test_compound_monthly(self, client: TestClient) -> None:
        payload = {"principal": 1000, "rate": 0.12, "years": 1, "compounding_frequency": 12}
        data = post(client, "/compound-interest", payload).json()
        assert data["future_value"] == pytest.approx(1000 * 1.01**12)
        assert data["interest"] == pytest.approx(1000 * 1.01**12 - 1000)

    def test_compound_continuous(self, client: TestClient) -> None:
        payload = {"principal": 1000, "rate": 0.12, "years": 1, "compounding": "continuous"}
        data = post(client, "/compound-interest", payload).json()
        assert data["future_value"] == pytest.approx(1000 * math.exp(0.12))

    def test_compound_invalid_frequency(self, client: TestClient) -> None:
        payload = {"principal": 1000, "rate": 0.12, "years": 1, "compounding_frequency": 0}
        assert post(client, "/compound-interest", payload).status_code == 422


class TestBondPrice:
    def test_semiannual_discount_bond(self, client: TestClient) -> None:
        data = post(client, "/bond-price", {**SEMI, "yield_to_maturity": 0.08}).json()

        assert data["price"] == pytest.approx(SEMI_AT_8)
        assert data["price_to_face"] == pytest.approx(SEMI_AT_8 / 1000)
        assert data["coupon_payment"] == pytest.approx(30)
        assert data["number_of_periods"] == 10
        assert data["periodic_yield"] == pytest.approx(0.04)
        assert len(data["cash_flows"]) == 10

    def test_zero_coupon_edge(self, client: TestClient) -> None:
        payload = {
            "face_value": 1000,
            "coupon_rate": 0,
            "years_to_maturity": 3,
            "coupon_frequency": 1,
            "yield_to_maturity": 0.10,
        }
        assert post(client, "/bond-price", payload).json()["price"] == pytest.approx(1000 / 1.331)

    def test_off_coupon_date_is_invalid(self, client: TestClient) -> None:
        response = post(
            client, "/bond-price", {**SEMI, "years_to_maturity": 5.1, "yield_to_maturity": 0.08}
        )
        assert response.status_code == 400
        assert "whole number" in response.json()["error"]["message"]


class TestYields:
    def test_ytm(self, client: TestClient) -> None:
        response = post(client, "/ytm", {**SEMI, "price": SEMI_AT_8})
        assert response.status_code == 200
        data = response.json()

        assert data["metric"] == "Yield to Maturity"
        assert data["value"] == pytest.approx(0.08, abs=1e-12)
        assert components(data)["Periodic Yield"] == pytest.approx(0.04, abs=1e-12)
        assert components(data)["Effective Annual Yield"] == pytest.approx(0.0816, abs=1e-12)

    def test_ytm_premium_bond_below_coupon(self, client: TestClient) -> None:
        data = post(client, "/ytm", {**SEMI, "price": 1100}).json()
        assert data["value"] < 0.06

    def test_ytm_invalid_price(self, client: TestClient) -> None:
        assert post(client, "/ytm", {**SEMI, "price": -5}).status_code == 422

    def test_ytc(self, client: TestClient) -> None:
        payload = {
            "face_value": 1000,
            "coupon_rate": 0.08,
            "years_to_maturity": 10,
            "coupon_frequency": 2,
            "price": 1100,
            "call_price": 1040,
            "years_to_call": 5,
        }
        data = post(client, "/ytc", payload).json()

        periodic = components(data)["Periodic Yield"]
        repriced = math.fsum(40 / (1 + periodic) ** k for k in range(1, 11))
        repriced += 1040 / (1 + periodic) ** 10
        assert data["metric"] == "Yield to Call"
        assert repriced == pytest.approx(1100)

    def test_ytc_beyond_maturity(self, client: TestClient) -> None:
        payload = {**SEMI, "price": 1000, "call_price": 1000, "years_to_call": 6}
        response = post(client, "/ytc", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"


class TestDurationAndSpreads:
    def test_duration_bundle_matches_single_endpoints(self, client: TestClient) -> None:
        payload = {**SEMI, "yield_to_maturity": 0.08}
        bundle = post(client, "/duration", payload).json()

        assert bundle["price"] == pytest.approx(SEMI_AT_8)
        for field, path in [
            ("macaulay_duration", "/macaulay-duration"),
            ("modified_duration", "/modified-duration"),
            ("convexity", "/convexity"),
        ]:
            assert bundle[field] == post(client, path, payload).json()["value"]

    def test_credit_spread(self, client: TestClient) -> None:
        payload = {**SEMI, "price": SEMI_AT_8, "risk_free_yield": 0.05}
        data = post(client, "/credit-spread", payload).json()

        assert data["value"] == pytest.approx(0.03, abs=1e-12)
        assert components(data)["Bond Yield to Maturity"] == pytest.approx(0.08, abs=1e-12)
        assert components(data)["Risk-free Yield"] == 0.05

    def test_negative_credit_spread_edge(self, client: TestClient) -> None:
        payload = {**SEMI, "price": SEMI_AT_8, "risk_free_yield": 0.09}
        assert post(client, "/credit-spread", payload).json()["value"] == pytest.approx(-0.01)


class TestCurveAndIrr:
    def test_spot_rates(self, client: TestClient) -> None:
        payload = {
            "coupon_frequency": 1,
            "instruments": [
                {"maturity_years": 2, "coupon_rate": 0.06, "price": 100},
                {"maturity_years": 1, "coupon_rate": 0.05, "price": 100},
            ],
        }
        data = post(client, "/spot-rates", payload).json()

        d1 = 100 / 105
        d2 = (100 - 6 * d1) / 106
        assert [p["maturity_years"] for p in data["points"]] == [1, 2]
        assert data["points"][0]["spot_rate"] == pytest.approx(0.05)
        assert data["points"][1]["discount_factor"] == pytest.approx(d2)
        assert data["points"][1]["spot_rate"] == pytest.approx(d2**-0.5 - 1)

    def test_spot_rates_gap_is_invalid(self, client: TestClient) -> None:
        payload = {
            "coupon_frequency": 1,
            "instruments": [
                {"maturity_years": 1, "coupon_rate": 0.05, "price": 100},
                {"maturity_years": 3, "coupon_rate": 0.06, "price": 100},
            ],
        }
        response = post(client, "/spot-rates", payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_INPUT"

    def test_irr(self, client: TestClient) -> None:
        data = post(client, "/irr", {"cash_flows": [-100, 110]}).json()
        assert data["metric"] == "IRR"
        assert data["value"] == pytest.approx(0.10)
        assert data["components"] == []

    def test_irr_annualized(self, client: TestClient) -> None:
        data = post(client, "/irr", {"cash_flows": [-100, 101], "periods_per_year": 12}).json()
        assert data["value"] == pytest.approx(0.01)
        assert components(data)["Effective Annual IRR"] == pytest.approx(1.01**12 - 1)

    def test_multiple_irrs_return_candidates(self, client: TestClient) -> None:
        response = post(client, "/irr", {"cash_flows": [-100, 230, -132]})

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "INVALID_INPUT"
        assert error["details"]["irr_candidates"] == pytest.approx([0.10, 0.20])

    def test_irr_needs_mixed_signs(self, client: TestClient) -> None:
        response = post(client, "/irr", {"cash_flows": [100, 200]})
        assert response.status_code == 400

    def test_irr_needs_two_flows(self, client: TestClient) -> None:
        assert post(client, "/irr", {"cash_flows": [-100]}).status_code == 422
