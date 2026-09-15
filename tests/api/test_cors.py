from tests.conftest import ClientFactory

PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "Content-Type",
}


def test_allowed_origin_receives_cors_headers(make_client: ClientFactory) -> None:
    client = make_client(cors_origins="http://jarvis.local")

    response = client.options(
        "/_test/ratio", headers={"Origin": "http://jarvis.local", **PREFLIGHT_HEADERS}
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://jarvis.local"


def test_disallowed_origin_is_not_granted(make_client: ClientFactory) -> None:
    client = make_client(cors_origins="http://jarvis.local")

    response = client.options(
        "/_test/ratio", headers={"Origin": "http://evil.example", **PREFLIGHT_HEADERS}
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_is_disabled_when_no_origins_configured(make_client: ClientFactory) -> None:
    client = make_client(cors_origins="")

    response = client.get("/health", headers={"Origin": "http://jarvis.local"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
