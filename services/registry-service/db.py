import functools
import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, Connection, Engine, create_engine, event, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.pool import NullPool

from problems import ProblemError

SERVICE_DIR = Path(__file__).parent
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
        return parsed.set(database=path.as_uri(), query={"mode": "rw", "uri": "true"})
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
    return create_engine(
        target,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={
            "connect_timeout": 3,
            "tcp_user_timeout": 10000,
            "keepalives": 1,
            "keepalives_idle": 10,
            "keepalives_interval": 5,
            "keepalives_count": 3,
        },
    )


def get_db() -> Iterator[Connection]:
    try:
        conn = get_engine(database_url()).connect()
    except (OperationalError, PoolTimeoutError) as exc:
        raise ProblemError(503, "Database unavailable") from exc
    try:
        yield conn
    finally:
        conn.close()  # also rolls back anything uncommitted


def exists(db: Connection, table: str, row_id: str) -> bool:
    return db.execute(text(f"SELECT 1 FROM {table} WHERE id = :id"), {"id": row_id}).first() is not None
