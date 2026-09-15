import json
import logging
from collections.abc import Iterator

import pytest

from app.core.logging import LOGGER_NAME, JsonFormatter
from tests.conftest import ClientFactory


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def captured(make_client: ClientFactory) -> Iterator[tuple[ClientFactory, _ListHandler]]:
    handler = _ListHandler()
    yield make_client, handler
    logging.getLogger(LOGGER_NAME).removeHandler(handler)


def _attach(handler: _ListHandler) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def test_access_log_contains_required_fields(
    captured: tuple[ClientFactory, _ListHandler],
) -> None:
    make_client, handler = captured
    client = make_client()
    _attach(handler)

    client.post("/_test/ratio", json={"numerator": 1, "denominator": 0})

    access = [r for r in handler.records if r.name == f"{LOGGER_NAME}.access"]
    assert len(access) == 1
    record = access[0].__dict__
    assert record["method"] == "POST"
    assert record["path"] == "/_test/ratio"
    assert record["status"] == 400
    assert record["duration_ms"] >= 0
    assert record["request_id"]


def test_access_log_never_contains_body_or_api_key(
    captured: tuple[ClientFactory, _ListHandler],
) -> None:
    make_client, handler = captured
    client = make_client(api_key="s3cret-key")
    _attach(handler)

    client.post(
        "/_test/ratio",
        json={"numerator": 123456789, "denominator": 1},
        headers={"X-API-Key": "s3cret-key"},
    )

    formatter = JsonFormatter()
    output = "\n".join(formatter.format(record) for record in handler.records)
    assert "s3cret-key" not in output
    assert "123456789" not in output


def test_unhandled_error_is_logged_with_traceback(
    captured: tuple[ClientFactory, _ListHandler],
) -> None:
    make_client, handler = captured
    client = make_client(raise_server_exceptions=False)
    _attach(handler)

    client.get("/_test/crash")

    errors = [r for r in handler.records if r.name == f"{LOGGER_NAME}.errors"]
    assert len(errors) == 1
    assert errors[0].exc_info is not None


def test_json_formatter_emits_valid_json_with_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "app.access", "levelname": "INFO", "msg": "request completed", "status": 200}
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "request completed"
    assert payload["status"] == 200
    assert payload["level"] == "INFO"
    assert "timestamp" in payload
