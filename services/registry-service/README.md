# registry-service

The AgroPilot registry: farms, plots, and read-only catalogues of crops, soils, and drip emitters. It runs on FastAPI with SQLAlchemy Core, against SQLite (local development and tests) or PostgreSQL (production).

## Run

```bash
uv sync
bash seed_registry.sh            # creates a fresh registry.db (deletes the old one)
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs.

## Configuration

The database is chosen by `DATABASE_URL`, read from the environment or from a `.env` file in this folder (a real environment variable wins). See `.env.example`.

- Default: `sqlite:///registry.db`. A relative SQLite path resolves against this folder. The app never creates the SQLite file; a missing file gives `503`.
- PostgreSQL: `DATABASE_URL=postgresql://user:password@host:5432/registry` (a bare `postgresql://` URL uses the psycopg driver).
- Special characters in a PostgreSQL password must be URL-encoded in `DATABASE_URL`.
- The production database should use UTF8 encoding.

### PostgreSQL setup

On a new, empty database:

```bash
uv run python scripts/setup_db.py
```

It creates the 5 tables and loads the catalogues (2 crops, 3 soils, 4 emitters), with no demo farms or plots. If any registry table already exists, it prints "Nothing changed" and exits without touching the database.

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
- `db.py`: `DATABASE_URL` handling, the SQLAlchemy engine, and the connection, one per request
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
