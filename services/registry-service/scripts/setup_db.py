"""One-off setup for a new, empty database: creates the schema and loads the seed:
2 crops, 3 soils, 4 emitters, 2 farms, 4 plots (the same 15 rows as seed_registry.sh).

Changes nothing if any registry table already exists.
Usage (from services/registry-service): uv run python scripts/setup_db.py
"""

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_DIR))

from config import ConfigError  # noqa: E402
from db import database_url, get_engine  # noqa: E402
from schema import existing_tables, load  # noqa: E402


def main(url: str | None = None) -> int:
    if url is None:
        try:
            url = database_url()
        except ConfigError as exc:
            print(exc, file=sys.stderr)
            return 2
    engine = get_engine(url)
    with engine.begin() as conn:
        found = existing_tables(conn)
        if found:
            print(f"Tables already exist: {', '.join(found)}. Nothing changed.", file=sys.stderr)
            return 1
        load(conn, "schema.sql", "catalogue.sql", "demo.sql")
    print("Created 5 tables and loaded 15 rows: 2 crops, 3 soils, 4 emitters, 2 farms, 4 plots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
