from fastapi.testclient import TestClient


def test_openapi_schema_documents_health_and_conventions(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "0.10" in schema["info"]["description"]


def test_error_responses_are_documented_with_envelope_model(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    responses = schema["paths"]["/_test/ratio"]["post"]["responses"]
    assert {"400", "422", "500"} <= set(responses)
    assert responses["400"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }


def test_swagger_and_redoc_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
