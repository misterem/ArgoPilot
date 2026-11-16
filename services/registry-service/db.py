import functools
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, event, make_url
from sqlalchemy.pool import NullPool

from problems import ProblemError

SERVICE_DIR = Path(__file__).parent
DEFAULT_DB_PATH = SERVICE_DIR / "registry.db"
DEFAULT_DATABASE_URL = "sqlite:///registry.db"


def load_env(path: Path = SERVICE_DIR / ".env") -> None:
    # override=False: a real environment variable beats the .env file.
    load_dotenv(path, override=False)


load_env()


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def engine_url(url: str) -> URL:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        # mode=rw: a missing file is an outage, not a cue to create an empty database.
        path = (SERVICE_DIR / (parsed.database or "registry.db")).resolve()
        return parsed.set(database=f"file:{path}", query={"mode": "rw", "uri": "true"})
    if parsed.drivername in ("postgresql", "postgres"):
        return parsed.set(drivername="postgresql+psycopg")
    return parsed


@functools.cache
def get_engine(url: str) -> Engine:
    target = engine_url(url)
    if target.get_backend_name() == "sqlite":
        engine = create_engine(target, poolclass=NullPool, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys = ON")

        return engine
    return create_engine(target, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def db_path() -> Path:
    return Path(os.environ.get("REGISTRY_DB", DEFAULT_DB_PATH)).resolve()


def get_db() -> Iterator[sqlite3.Connection]:
    # mode=rw: a missing file is an outage, not a cue to create an empty database.
    try:
        conn = sqlite3.connect(f"{db_path().as_uri()}?mode=rw", uri=True, check_same_thread=False)
    except sqlite3.OperationalError as exc:
        raise ProblemError(503, "Database unavailable") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def exists(db: sqlite3.Connection, table: str, row_id: str) -> bool:
    return db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)).fetchone() is not None
