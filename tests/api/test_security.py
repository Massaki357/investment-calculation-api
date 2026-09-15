from tests.conftest import ClientFactory

PAYLOAD = {"numerator": 10, "denominator": 2}


def test_authentication_is_disabled_by_default(make_client: ClientFactory) -> None:
    client = make_client()

    assert client.post("/_test/ratio", json=PAYLOAD).status_code == 200


def test_missing_api_key_is_rejected_when_enabled(make_client: ClientFactory) -> None:
    client = make_client(api_key="s3cret")

    response = client.post("/_test/ratio", json=PAYLOAD)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_wrong_api_key_is_rejected_when_enabled(make_client: ClientFactory) -> None:
    client = make_client(api_key="s3cret")

    response = client.post("/_test/ratio", json=PAYLOAD, headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
    assert "s3cret" not in response.text


def test_correct_api_key_is_accepted_when_enabled(make_client: ClientFactory) -> None:
    client = make_client(api_key="s3cret")

    response = client.post("/_test/ratio", json=PAYLOAD, headers={"X-API-Key": "s3cret"})

    assert response.status_code == 200


def test_health_never_requires_api_key(make_client: ClientFactory) -> None:
    client = make_client(api_key="s3cret")

    assert client.get("/health").status_code == 200
