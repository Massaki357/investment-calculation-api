from fastapi.testclient import TestClient

from tests.conftest import ClientFactory


def _assert_envelope(body: dict, code: str) -> None:
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)


def test_successful_calculation_through_full_pipeline(client: TestClient) -> None:
    response = client.post("/_test/ratio", json={"numerator": 35.5, "denominator": 4.2})

    assert response.status_code == 200
    assert response.json() == {
        "metric": "ratio",
        "value": 35.5 / 4.2,
        "unit": "multiple",
        "currency": None,
    }


def test_result_is_not_rounded(client: TestClient) -> None:
    response = client.post("/_test/ratio", json={"numerator": 1, "denominator": 3})

    assert response.json()["value"] == 1 / 3


def test_domain_error_returns_400_envelope(client: TestClient) -> None:
    response = client.post("/_test/ratio", json={"numerator": 1, "denominator": 0})

    assert response.status_code == 400
    _assert_envelope(response.json(), "DIVISION_BY_ZERO")
    assert response.json()["error"]["message"] == "denominator cannot be zero"


def test_raised_domain_exception_is_translated(client: TestClient) -> None:
    response = client.get("/_test/domain-error")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "DIVISION_BY_ZERO",
            "message": "earnings_per_share cannot be zero",
            "details": None,
        }
    }


def test_unknown_route_returns_404_envelope(client: TestClient) -> None:
    response = client.post("/api/v1/does-not-exist", json={})

    assert response.status_code == 404
    _assert_envelope(response.json(), "NOT_FOUND")


def test_wrong_method_returns_405_envelope(client: TestClient) -> None:
    response = client.post("/health")

    assert response.status_code == 405
    _assert_envelope(response.json(), "METHOD_NOT_ALLOWED")
    assert "GET" in response.headers["allow"]


def test_schema_violation_returns_422_with_field_details(client: TestClient) -> None:
    response = client.post("/_test/ratio", json={"numerator": "abc"})

    assert response.status_code == 422
    body = response.json()
    _assert_envelope(body, "VALIDATION_ERROR")
    fields = {detail["field"] for detail in body["error"]["details"]}
    assert fields == {"body.numerator", "body.denominator"}


def test_422_details_never_echo_submitted_input(client: TestClient) -> None:
    response = client.post(
        "/_test/ratio", json={"numerator": "sensitive-value-123", "denominator": 1}
    )

    assert response.status_code == 422
    assert "sensitive-value-123" not in response.text


def test_unknown_fields_are_rejected(client: TestClient) -> None:
    response = client.post("/_test/ratio", json={"numerator": 1, "denominator": 2, "denominatr": 3})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "extra_forbidden"


def test_nan_and_infinity_inputs_are_rejected(client: TestClient) -> None:
    for literal in ("NaN", "Infinity", "-Infinity"):
        response = client.post(
            "/_test/ratio",
            content=f'{{"numerator": {literal}, "denominator": 1}}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, literal
        _assert_envelope(response.json(), "VALIDATION_ERROR")


def test_malformed_json_returns_400(client: TestClient) -> None:
    response = client.post(
        "/_test/ratio",
        content='{"numerator": 1,',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    _assert_envelope(response.json(), "MALFORMED_REQUEST")


def test_unhandled_exception_returns_500_without_internals(make_client: ClientFactory) -> None:
    client = make_client(raise_server_exceptions=False)

    response = client.get("/_test/crash")

    assert response.status_code == 500
    _assert_envelope(response.json(), "INTERNAL_ERROR")
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert "X-Request-ID" in response.headers
