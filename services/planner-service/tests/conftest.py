import os

import pytest
from fastapi.testclient import TestClient

# Every required variable, overwriting the shell, so a developer's .env or exports never change test results.
TEST_ENV = {
    "REGISTRY_URL": "http://registry.test",
    "WEATHER_URL": "http://weather.test",
    "REGISTRY_TIMEOUT_S": "5",
    "WEATHER_TIMEOUT_S": "20",
}
os.environ.update(TEST_ENV)

import config  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch):
    for name, value in TEST_ENV.items():
        monkeypatch.setenv(name, value)
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def assert_problem(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["status"] == status
    assert body["code"] == code
    assert body["title"] and body["detail"]
    return body
