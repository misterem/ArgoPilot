# registry-service

The AgroPilot registry: farms, plots, and read-only catalogues of crops, soils, and drip emitters. It runs on FastAPI with SQLAlchemy Core, against SQLite (local development and tests) or PostgreSQL (production).

## Run

```bash
uv sync
cp .env.example .env           # DATABASE_URL is required; the example uses SQLite
bash seed_registry.sh            # creates a fresh registry.db (deletes the old one)
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs.

## Configuration

The database is chosen by `DATABASE_URL`, read by `config.py` (pydantic-settings) from the environment or from a `.env` file in this folder (a real environment variable wins). See `.env.example`.

`DATABASE_URL` is required and has no default. If it is missing or empty, the service and `scripts/setup_db.py` stop at startup with `DATABASE_URL is not set. Copy .env.example to .env ...`.

- SQLite (local development): `DATABASE_URL=sqlite:///registry.db`. A relative SQLite path resolves against this folder. The app never creates the SQLite file; a missing file gives `503`.
- PostgreSQL: `DATABASE_URL=postgresql://user:password@host:5432/registry` (a bare `postgresql://` URL uses the psycopg driver).
- Special characters in a PostgreSQL password must be URL-encoded in `DATABASE_URL`.
- The production database should use UTF8 encoding.

**Switching between SQLite and PostgreSQL** is a configuration change only. Keep both lines in `.env`, with exactly one active, and comment one out to switch:

```
# Local development:
DATABASE_URL=sqlite:///registry.db
# Production (PostgreSQL):
# DATABASE_URL=postgresql://user:password@localhost:5432/registry
```

If both lines are active, the last one silently wins, so always comment one out. A `DATABASE_URL` set in the shell overrides both. Tests ignore `.env`: each test builds its own fresh SQLite copy (or uses `TEST_POSTGRES_URL`, see Test).

### PostgreSQL setup

On a new, empty database, with `DATABASE_URL` pointing at it:

```bash
uv run python scripts/setup_db.py
```

On a Mac, a local "production" database (no password; Homebrew's server trusts local connections from your user):

```bash
brew install postgresql@16
brew services start postgresql@16
/opt/homebrew/opt/postgresql@16/bin/createdb registry
# .env: DATABASE_URL=postgresql://<your macOS user>@localhost:5432/registry
uv run python scripts/setup_db.py
```

It creates the 5 tables and loads the same 15 rows as `seed_registry.sh`: 2 crops, 3 soils, 4 emitters, 2 farms, 4 plots. If any registry table already exists, it prints "Nothing changed" and exits without touching the database.

### Performance on PostgreSQL

Measured 2026-11-17 on PostgreSQL 16.16 (Homebrew, local), `scripts/measure_latency.py --seconds 60`, 10 requests per second, 600 requests across the list and get-by-id routes of farms, plots and the catalogues:

| | p50 | p95 | max |
| --- | --- | --- | --- |
| All routes | 6.9 ms | 10.7 ms | 29.0 ms |
| Slowest route by p95 (`/v1/crops`) | 6.9 ms | 11.7 ms | 12.7 ms |

Target (NFR-1.1 / NFR-2.2): p95 ≤ 100 ms.

## API

| Resource | Routes |
| --- | --- |
| Farms | `POST/GET /v1/farms`, `GET/PATCH/DELETE /v1/farms/{id}`, `GET /v1/farms/{id}/area` (total plot area, `{"area_m2": ...}`) |
| Plots | `POST/GET /v1/plots` (`?farm_id=` filters), `GET/PATCH/DELETE /v1/plots/{id}` |
| Catalogues | `GET /v1/crops[/{id}]`, `GET /v1/soils[/{id}]`, `GET /v1/emitters[/{id}]` |

`PATCH` changes only the fields you send. Catalogues are read-only, so any other method returns `405`.

Every error is `application/problem+json` (RFC 9457) with a `code`:

| Status | `code` | When |
| --- | --- | --- |
| 422 | `VALIDATION` | Bad or missing field, unknown farm/crop/soil/emitter, malformed JSON |
| 405 | `VALIDATION` | Writing to a catalogue route |
| 404 | `NOT_FOUND` | Unknown id or route |
| 409 | `CONFLICT` | Duplicate plot name on one farm; deleting a farm that has plots |
| 503 | `UNAVAILABLE` | Database missing, unreachable, or without tables (sends `Retry-After`) |

## Code layout

- `main.py`: builds the app and wires in the routers
- `farms.py`, `plots.py`, `catalogue.py`: the routes
- `models.py`: request and response models and their validation rules
- `problems.py`: the problem+json error responses
- `config.py`: settings (`DATABASE_URL`), read with pydantic-settings; stops startup when one is missing
- `db.py`: URL handling (SQLite path, psycopg driver), the SQLAlchemy engine, and the connection, one per request
- `db_errors.py`: tells "database unavailable" and "unique violation" apart across SQLite and PostgreSQL
- `schema.py`: loads the SQL files into a connection; used by `scripts/setup_db.py` and the test fixture
- `schema.sql`, `catalogue.sql`, `demo.sql`: the tables, the catalogue rows, and the demo farms and plots, shared by both databases

## Test

```bash
uv run pytest
```

Each test runs against a freshly seeded copy of the database in a temp folder, so `registry.db` is never touched.

To run the suite against PostgreSQL as well, start a throwaway server and set `TEST_POSTGRES_URL`:

```bash
docker run --rm -d --name registry-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
TEST_POSTGRES_URL=postgresql://postgres:pg@127.0.0.1:55432/postgres uv run pytest
```

Warning: before every test the fixture runs `DROP SCHEMA public CASCADE` on that database. Use a throwaway database only.

## Latency (NFR-1.1)

With the server running:

```bash
uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --seconds 60
```

It sends 10 req/s round-robin across every list and get-by-id route and prints p50/p95/max.
