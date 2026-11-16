# registry-service: SQLite locally, PostgreSQL in production

Date: 2026-11-16 · Status: draft, awaiting approval

## Intent

Let the registry run on a real database. Locally and in tests it keeps using the SQLite file `registry.db`. In production it runs on PostgreSQL. `DATABASE_URL`, read from the environment or a `.env` file, picks the database. Clients must not be able to tell which one is in use.

## Goals

- Every existing endpoint behaves exactly as it does today on both databases: same status codes, same `application/problem+json` bodies and `code`s, same `Retry-After` on 503, and the same JSON values and types.
- `DATABASE_URL` selects the database. It comes from the process environment or from a `.env` file in the service folder.
- There's a way to set up a new, empty Postgres database with the schema and the catalogue rows.

## Non-goals

- No new endpoints, fields, or API features (the CLAUDE.md spec rule).
- No migration tool (Alembic) and no ORM models. The schema stays hand-written SQL.
- No moving data from an existing SQLite file into Postgres.
- No demo farms or plots in production.

## Anti-goals (a failure even if it "works")

- A missing database or missing tables silently get created. A missing SQLite file must still return 503 and must not leave an empty file behind. A Postgres database without tables must also return 503.
- The two databases return different JSON, such as `"area_m2": 0` on one and `0.0` on the other, or a different date format.
- The Postgres and SQLite schemas drift apart.
- An unreachable Postgres server makes requests hang instead of quickly returning 503.

## Constraints

- Python 3.12 and 3.14 must both work.
- Flat modules imported by bare name, and uvicorn starts from the service folder (unchanged).
- The production Postgres database doesn't exist yet. It'll be created empty, and the setup step below fills it.
- On day one, production holds the same catalogue rows as the seed (2 crops, 3 soils, 4 emitters) and no farms or plots. *(Decided by the user.)*
- The `psql` CLI isn't installed locally, and the deploy machine may not have it either. Docker is available locally.

## Approaches

| | Approach | Trade-off |
|---|---|---|
| **A (picked)** | **SQLAlchemy Core.** `DATABASE_URL` becomes an engine, and the routes keep their raw SQL via `text()` with the same `:name` params. | One well-known dependency gives both databases portable parameters, the same error classes, and connection pooling. Changes to the routes are small. |
| B | Own thin adapter over `sqlite3` + `psycopg` | No SQLAlchemy, but we'd write and maintain param translation, row dicts, error mapping and pooling ourselves. More places where the two backends could quietly differ. |
| C (dropped) | ORM (SQLAlchemy ORM / SQLModel) | Rewrites every route. The highest risk to "behaves exactly the same". |

**The user picked A.**

## Design

### Configuration (`db.py`)

- On import, `db.py` loads `.env` from the service folder with `python-dotenv` (`override=False`, so a real environment variable wins over `.env`). *(My call.)*
- `DATABASE_URL` replaces `REGISTRY_DB`. When it isn't set, the default is `sqlite:///registry.db`, so local runs behave as they do today. *(My call.)*
- SQLite URLs: a relative path resolves against the service folder, as `DEFAULT_DB_PATH` does today. The app always opens the file read-write only, never creating it (`sqlite:///file:<abs path>?mode=rw&uri=true`). Users write the plain `sqlite:///registry.db` form, and the app adds `mode=rw` itself. *(My call.)*
- Postgres URLs: `postgresql+psycopg://user:pass@host:5432/db`. A bare `postgresql://` is rewritten to use the `psycopg` driver (psycopg 3). *(My call.)*
- The engine is built lazily and cached per URL. The tests change `DATABASE_URL` between tests, so the app reads the env var on each request, as it reads `REGISTRY_DB` today, and reuses the engine for that URL.
- Engine options:
  - SQLite: a connect hook runs `PRAGMA foreign_keys = ON`, plus `check_same_thread=False`.
  - Postgres: `pool_pre_ping=True`, so a connection that died during a server restart is replaced instead of failing the request, and `connect_timeout=3` so an unreachable server gives 503 quickly. *(Values are my call.)*
- `.env.example` is committed with a commented SQLite line and a commented Postgres line. `.env` is already gitignored.

### Connection dependency

- `get_db` yields a SQLAlchemy `Connection` per request and closes it afterwards. A failed connect raises `ProblemError(503, "Database unavailable")`, as it does today.
- Routes swap `with db:` for `with db.begin():` on writes. Reads stay as they are. The builder makes sure SQLAlchemy 2.0's autobegin doesn't leave a read transaction open around a later `begin()` (for example by committing or rolling back after reads, or by using `db.begin()` consistently).
- Rows are returned as `dict(row._mapping)`.

### SQL changes in routes

- `TOTAL(area_m2)` → `COALESCE(SUM(area_m2), 0.0)`, which gives a float on both databases. `area_m2` for a farm with no plots must still be `0.0`, as it is today.
- Positional `?` params become named `:param`s inside `text()`.
- `db.exists` keeps its table-name f-string (the table names come from code constants, never from input).

### Errors (`problems.py`, `plots.py`, `farms.py`)

- 409 on duplicate plot name: catch `sqlalchemy.exc.IntegrityError` and look at `exc.orig`:
  - Postgres: SQLSTATE `23505` (`UniqueViolation`).
  - SQLite: a message containing `UNIQUE`.

  Any other integrity error keeps today's behaviour (re-raised). Put this in one small helper (e.g. `db.is_unique_violation(exc)`) so the routes don't know which database they're on.
- 409 when deleting a farm that has plots (the race path): catch `sqlalchemy.exc.IntegrityError` (an FK violation on both databases).
- 503 mapping in `problems.install`, replacing the `sqlite3.OperationalError` handler:
  - `sqlalchemy.exc.OperationalError` → 503 (connection failures; SQLite's missing table or bad file).
  - `sqlalchemy.exc.ProgrammingError` whose `orig` is a Postgres undefined table (SQLSTATE `42P01`) → 503, so a Postgres database without tables gives the same answer as an empty SQLite file. Other `ProgrammingError`s are bugs and stay 500.
  - `sqlalchemy.exc.InterfaceError` / `DBAPIError` with `connection_invalidated=True` → 503.
- Every 503 still carries `Retry-After`, through the existing `problem()`.

### Schema and seed files

Split the heredoc in `seed_registry.sh` into three SQL files in the service folder:

- `schema.sql`: the five tables, written in DDL both databases accept. Use `DOUBLE PRECISION` in place of `REAL`, because Postgres `REAL` is 4-byte and would change values like `0.6`. SQLite treats `DOUBLE PRECISION` as REAL affinity, so SQLite behaves the same. Keep `TEXT` for ids and `planting_date`, and `INTEGER` for `available_water_mm_per_m`. Same `UNIQUE (farm_id, name)` and foreign keys.
- `catalogue.sql`: the crop, soil and emitter rows.
- `demo.sql`: the 2 farms and 4 plots.

One schema file serves both databases, so they can't drift and no comparison test is needed.

- `seed_registry.sh` (SQLite, local and tests): same usage and behaviour as today (deletes the file, then runs `PRAGMA foreign_keys = ON` + `schema.sql` + `catalogue.sql` + `demo.sql` through the `sqlite3` CLI).
- `scripts/setup_db.py` (new, for Postgres): reads `DATABASE_URL` (env or `.env`) and runs `schema.sql` + `catalogue.sql` in one transaction through SQLAlchemy, so no `psql` is needed. It is **not destructive**: if any of the tables already exist it stops with a clear message and changes nothing. It never loads demo data. *(My call: Python instead of a psql script, because psql isn't a given.)*

### Dependencies

Add to `pyproject.toml`: `sqlalchemy~=2.0`, `psycopg[binary]~=3.2`, `python-dotenv~=1.0` (the builder pins the exact versions that resolve). Update `uv.lock`.

### Tests

- The default suite stays on SQLite, unchanged in what it checks. The `client` fixture sets `DATABASE_URL=sqlite:///<tmp>/registry.db` in place of `REGISTRY_DB`. The 503 tests in `test_errors.py` and `test_farms.py` switch to `DATABASE_URL` the same way, still asserting that no file gets created.
- New tests:
  - `.env` is read, and a real env var beats `.env`.
  - A relative `sqlite:///` path resolves against the service folder.
  - `setup_db.py` refuses to run on a database that already has tables.
- **Postgres run (opt-in):** when `TEST_POSTGRES_URL` is set, the same suite runs against Postgres. The fixture runs `schema.sql` + `catalogue.sql` + `demo.sql` into a fresh database (or a dropped and recreated `public` schema) for each test. When the variable isn't set, these tests are skipped. Locally that means a throwaway Docker container (`postgres:16`). The Postgres versions of the 503 tests are: unreachable host, and database without tables. *(My call: this is how requirement 1 gets proven on Postgres, not just on SQLite.)*

### Docs

- README: the `DATABASE_URL` and `.env` setup, the Postgres setup command, and the opt-in Postgres test run. Drop `REGISTRY_DB`.
- CLAUDE.md: update the "seed script owns the schema" and "DB connection" bullets and the test-fixture note to match.
- `docs/judgment-log.md` is not touched by this work. *(Decided by the user.)*

## Left to the builder

- Exact pinned versions and how the engine cache is keyed.
- Transaction handling details under SQLAlchemy 2.0 autobegin, as long as writes are atomic and no request leaves a transaction open.
- How the Postgres test fixture isolates tests (a database per test, or a schema reset), as long as each test starts from the seed.
- Load the `registry-api` skill before touching `problems.py` and the route modules.
