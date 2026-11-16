import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from problems import ProblemError

DEFAULT_DB_PATH = Path(__file__).parent / "registry.db"


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
