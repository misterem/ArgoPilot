import os
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
import problems
from conftest import TEST_ENV, assert_problem


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_is_problem(client):
    assert_problem(client.get("/nope"), 404, "NOT_FOUND")


def test_settings_load(tmp_path):
    s = config.load_settings(tmp_path / "absent.env")
    assert (s.registry_url, s.weather_url, s.registry_timeout_s, s.weather_timeout_s) == (
        "http://registry.test", "http://weather.test", 5, 20)


def test_missing_variable_is_named(tmp_path, monkeypatch):
    monkeypatch.delenv("WEATHER_URL")
    with pytest.raises(config.ConfigError, match="WEATHER_URL is not set"):
        config.load_settings(tmp_path / "absent.env")


def test_empty_url_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRY_URL", "")
    with pytest.raises(config.ConfigError, match="REGISTRY_URL is not set"):
        config.load_settings(tmp_path / "absent.env")


def test_invalid_value_is_named(tmp_path, monkeypatch):
    monkeypatch.setenv("REGISTRY_TIMEOUT_S", "0")
    with pytest.raises(config.ConfigError, match="REGISTRY_TIMEOUT_S is invalid"):
        config.load_settings(tmp_path / "absent.env")


def test_problem_code_override():
    app = FastAPI()
    problems.install(app)

    @app.get("/boom")
    def boom():
        raise problems.ProblemError(503, "weather-service unavailable: x", code="UPSTREAM_UNAVAILABLE")

    assert_problem(TestClient(app).get("/boom"), 503, "UPSTREAM_UNAVAILABLE")


def test_service_exits_at_startup_without_config(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in TEST_ENV}
    code = f"import config, pathlib; config.ENV_FILE = pathlib.Path({str(tmp_path / 'absent.env')!r}); import main"
    result = subprocess.run([sys.executable, "-c", code], cwd=config.SERVICE_DIR, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "planner-service: " in result.stderr
    assert "REGISTRY_URL" in result.stderr
    assert "Traceback" not in result.stderr
