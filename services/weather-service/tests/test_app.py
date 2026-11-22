import os
import subprocess
import sys

import pytest

import config
from conftest import TEST_ENV, assert_problem


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_unknown_route_is_problem(client):
    assert_problem(client.get("/nope"), 404, "NOT_FOUND")


def test_settings_load_from_environment(tmp_path):
    s = config.load_settings(tmp_path / "absent.env")
    assert s.provider_base_url == "https://provider.test"
    assert s.provider_retries == 2
    assert s.forecast_max_stale_hours == 24


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("PROVIDER_TIMEOUT_S")
    (tmp_path / ".env").write_text("PROVIDER_TIMEOUT_S=7\n")
    assert config.load_settings(tmp_path / ".env").provider_timeout_s == 7


def test_missing_variable_is_named(tmp_path, monkeypatch):
    monkeypatch.delenv("PROVIDER_TIMEOUT_S")
    with pytest.raises(config.ConfigError, match="PROVIDER_TIMEOUT_S is not set"):
        config.load_settings(tmp_path / "absent.env")


def test_empty_api_key_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_API_KEY", "")
    assert config.load_settings(tmp_path / "absent.env").provider_api_key == ""


def test_api_key_must_be_present(tmp_path, monkeypatch):
    monkeypatch.delenv("PROVIDER_API_KEY")
    with pytest.raises(config.ConfigError, match="PROVIDER_API_KEY"):
        config.load_settings(tmp_path / "absent.env")


def test_empty_base_url_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_BASE_URL", "")
    with pytest.raises(config.ConfigError, match="PROVIDER_BASE_URL"):
        config.load_settings(tmp_path / "absent.env")


def test_invalid_value_is_named(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_RETRIES", "-1")
    with pytest.raises(config.ConfigError, match="PROVIDER_RETRIES is invalid"):
        config.load_settings(tmp_path / "absent.env")


def test_unknown_env_vars_are_ignored(tmp_path):
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///x.db\n")
    assert config.load_settings(tmp_path / ".env").retry_after_s == 60


def test_service_exits_at_startup_without_config(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in TEST_ENV}
    code = f"import config, pathlib; config.ENV_FILE = pathlib.Path({str(tmp_path / 'absent.env')!r}); import main"
    result = subprocess.run([sys.executable, "-c", code], cwd=config.SERVICE_DIR, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "weather-service: " in result.stderr
    assert "PROVIDER_BASE_URL" in result.stderr
    assert "Traceback" not in result.stderr


def test_max_stale_over_24h_is_invalid(tmp_path, monkeypatch):
    # forecast_days=8 only covers today + 6 for a forecast up to 24 h old; more would silently 503.
    monkeypatch.setenv("FORECAST_MAX_STALE_HOURS", "48")
    with pytest.raises(config.ConfigError, match="FORECAST_MAX_STALE_HOURS is invalid"):
        config.load_settings(tmp_path / "absent.env")


def test_fresh_window_longer_than_stale_limit_is_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("FORECAST_FRESH_HOURS", "30")
    with pytest.raises(config.ConfigError, match="FORECAST_FRESH_HOURS"):
        config.load_settings(tmp_path / "absent.env")
