import subprocess

import pytest

import sqlalchemy.exc
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError, ProgrammingError

import config
import db
import db_errors
import schema
from conftest import assert_problem
from main import app


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    assert config.load_settings(tmp_path / ".env").database_url == "sqlite:///from-file.db"


def test_real_env_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-env.db")
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    assert config.load_settings(tmp_path / ".env").database_url == "sqlite:///from-env.db"


def test_missing_url_raises_config_error(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(config.ConfigError, match="DATABASE_URL"):
        config.load_settings(tmp_path / "absent.env")


def test_empty_url_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=\n")
    with pytest.raises(config.ConfigError, match="DATABASE_URL"):
        config.load_settings(tmp_path / ".env")


def test_unknown_env_vars_are_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///x.db\nWEATHER_URL=http://x\n")
    assert config.load_settings(tmp_path / ".env").database_url == "sqlite:///x.db"


def test_database_url_comes_from_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///via-settings.db")
    config.get_settings.cache_clear()
    assert db.database_url() == "sqlite:///via-settings.db"


def test_relative_sqlite_path_resolves_to_service_dir():
    url = db.engine_url("sqlite:///registry.db")
    assert url.database == (db.SERVICE_DIR / 'registry.db').resolve().as_uri()
    assert url.query == {"mode": "rw", "uri": "true"}


def test_bare_postgres_url_gets_psycopg_driver():
    assert db.engine_url("postgresql://u:p@h:5432/d").drivername == "postgresql+psycopg"
    assert db.engine_url("postgres://u:p@h:5432/d").drivername == "postgresql+psycopg"


def test_statements_split_schema():
    assert len(schema.statements("schema.sql")) == 5


class FakeOrig(Exception):
    def __init__(self, sqlstate=None, message=""):
        super().__init__(message)
        self.sqlstate = sqlstate


def test_is_unavailable_classification():
    missing_table = ProgrammingError("stmt", {}, FakeOrig("42P01"))
    syntax_error = ProgrammingError("stmt", {}, FakeOrig("42601"))
    assert db_errors.is_unavailable(missing_table)
    assert not db_errors.is_unavailable(syntax_error)
    assert db_errors.is_unavailable(OperationalError("stmt", {}, FakeOrig()))
    assert db_errors.is_unavailable(InterfaceError("stmt", {}, FakeOrig()))
    invalidated = IntegrityError("stmt", {}, FakeOrig(), connection_invalidated=True)
    assert db_errors.is_unavailable(invalidated)
    assert not db_errors.is_unavailable(IntegrityError("stmt", {}, FakeOrig("23505")))


def test_is_unique_violation_classification():
    assert db_errors.is_unique_violation(IntegrityError("stmt", {}, FakeOrig("23505")))
    sqlite_style = IntegrityError("stmt", {}, FakeOrig(None, "UNIQUE constraint failed: plots.name"))
    assert db_errors.is_unique_violation(sqlite_style)
    assert not db_errors.is_unique_violation(IntegrityError("stmt", {}, FakeOrig("23503", "fk")))


def _seed(path):
    subprocess.run(["bash", str(db.SERVICE_DIR / "seed_registry.sh"), str(path)], check=True, capture_output=True)


def test_sqlite_foreign_keys_are_enforced(tmp_path):
    path = tmp_path / "fk.db"
    _seed(path)
    with db.get_engine(f"sqlite:///{path}").connect() as c:
        assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_sqlite_path_with_special_characters(tmp_path, monkeypatch):
    folder = tmp_path / "a #b"
    folder.mkdir()
    path = folder / "registry.db"
    _seed(path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    with TestClient(app) as c:
        assert c.get("/v1/farms").status_code == 200


class _TimingOutEngine:
    def connect(self):
        raise sqlalchemy.exc.TimeoutError("QueuePool limit reached")


def test_pool_timeout_gives_503(monkeypatch):
    monkeypatch.setattr(db, "get_engine", lambda url: _TimingOutEngine())
    with TestClient(app) as c:
        response = c.get("/v1/farms")
    assert_problem(response, 503, "UNAVAILABLE")
    assert response.headers["retry-after"].isdigit()


def test_postgres_engine_pool_timeout():
    assert db.get_engine("postgresql://u:p@127.0.0.1:1/x").pool.timeout() == 5
