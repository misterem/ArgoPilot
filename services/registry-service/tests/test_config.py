from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError, ProgrammingError

import db
import db_errors
import schema


def test_default_url_is_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.database_url() == "sqlite:///registry.db"


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    db.load_env(tmp_path / ".env")
    assert db.database_url() == "sqlite:///from-file.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)  # load_env set it outside monkeypatch


def test_real_env_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-env.db")
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    db.load_env(tmp_path / ".env")
    assert db.database_url() == "sqlite:///from-env.db"


def test_relative_sqlite_path_resolves_to_service_dir():
    url = db.engine_url("sqlite:///registry.db")
    assert url.database == f"file:{db.SERVICE_DIR / 'registry.db'}"
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
