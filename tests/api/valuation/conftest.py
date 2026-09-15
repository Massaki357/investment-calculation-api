import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(module_client: TestClient) -> TestClient:
    return module_client
