# Registry for P2: full seed on setup, required config — design

Part 1 of P2 (`tasks/p2.md`, registry section and "Global configurations"). Small change on top of the Postgres support already merged (`2026-11-16-postgres-support-design.md`).

## Intent

P2 makes the registry production-ready on PostgreSQL in the way the spec asks: a new environment is built from nothing with one command (FR-2.2), moving between SQLite and PostgreSQL is configuration only (NFR-2.1), and every service reads its settings the same way and refuses to start without them.

## Goals

- **FR-2.2:** `uv run python scripts/setup_db.py` on an empty database creates the tables and loads the same 15 rows as `seed_registry.sh`: 2 crops, 3 soils, 4 emitters, 2 farms, 4 plots. *(Decided by the user: the spec wins over the earlier catalogue-only decision.)*
- **Config:** `config.py` with a pydantic-settings `Settings` holding `DATABASE_URL`, read from the environment or `.env` in the service folder (a real environment variable wins, as today).
- **`DATABASE_URL` is required.** *(Decided by the user.)* With it missing, the service and `setup_db.py` stop at startup with a clear message naming the variable and pointing at `.env.example`, never on the first request.
- **NFR-2.2:** run the service against the local PostgreSQL `registry` database and measure `GET` list and `GET` by id with `scripts/measure_latency.py` (10 rps); p95 ≤ 100 ms. Record the numbers in the README.

## Non-goals

- No new endpoints, fields, or schema changes.
- No judgment-log entry for this part. *(User.)*
- No migration tool; `schema.sql` still owns the schema.

## Approach

One sensible way; the only real choice was required vs defaulted `DATABASE_URL`, and the user chose required (a defaulted one lets production silently run on SQLite).

- `setup_db.py` loads `schema.sql`, `catalogue.sql`, `demo.sql` in one transaction. The "refuse if any registry table exists, change nothing" guard stays. Messages and docstring say 15 rows.
- `config.py` replaces the `python-dotenv` code in `db.py`; `python-dotenv` comes out of the dependencies and `pydantic-settings` goes in.
- Settings are read when needed (a cached getter the tests can reset, or a fresh read), not frozen at import, because the test fixture sets `DATABASE_URL` per test with `monkeypatch`.
- The startup check runs when the app is built (`main.py`), so `uvicorn main:app` fails before serving.
- `.env.example`: the SQLite line uncommented (works after `cp .env.example .env`), the PostgreSQL line as a commented example.
- Docs: README (run steps include `cp .env.example .env`, setup loads 15 rows, measured p95 on Postgres), CLAUDE.md (config bullet, the "default `sqlite:///registry.db`" statement).

## Constraints

- Python 3.12 and 3.14 both.
- Existing test suite keeps passing on SQLite and with `TEST_POSTGRES_URL`.
- Relative SQLite paths still resolve against the service folder; `mode=rw` behaviour unchanged.

## Left to the builder

- Exact error message wording and exit mechanism, as long as it names `DATABASE_URL` and happens at startup.
- Tests: missing `DATABASE_URL` fails at startup; `setup_db.py` on an empty DB yields the 15 rows; the guard still refuses on a non-empty DB.
