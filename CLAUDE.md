# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AgroPilot helps growers manage crops. Services live under `services/`; today there is one, `registry-service` (FastAPI + SQLAlchemy Core on SQLite or PostgreSQL): farms, plots, and read-only crop/soil/emitter catalogues.

## Commands

Run everything from `services/registry-service` (uv project, `package = false`):

```bash
uv sync                                   # install, including dev group (pytest, httpx)
bash seed_registry.sh                     # recreate registry.db from scratch (needs the sqlite3 CLI)
uv run python scripts/setup_db.py         # new empty DB (e.g. Postgres): schema + catalogues, refuses if tables exist
uv run uvicorn main:app --host 127.0.0.1 --port 8000
uv run pytest                             # all tests
uv run pytest tests/test_plots.py::test_patch_changes_only_sent_fields   # one test
uv run pytest -k duplicate                # by name
# Postgres run: docker run --rm -d --name registry-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
TEST_POSTGRES_URL=postgresql://postgres:pg@127.0.0.1:55432/postgres uv run pytest   # DROPs schema public before every test: throwaway DB only
uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --seconds 60   # NFR p95 check
```

There is no linter or formatter configured.

## Architecture (registry-service)

- **Flat modules, imported by bare name** (`import farms`, `from db import get_db`). There is no package; `pyproject.toml` sets pytest `pythonpath = ["."]`, and uvicorn must be started from the service folder.
- **`schema.sql` owns the schema**, shared by SQLite and PostgreSQL (with `catalogue.sql` and `demo.sql`; `seed_registry.sh` pipes them into the `sqlite3` CLI, and `schema.py` loads them for `scripts/setup_db.py` and the tests). No migrations or ORM models: the tables, the `UNIQUE (farm_id, name)` on plots, and the foreign keys come from that file, and the code uses plain SQL through SQLAlchemy Core against them. A schema change means editing `schema.sql` and the matching pydantic models in `models.py`. SQL column lists are built from the response models' fields (`Plot.model_fields`), so the two must stay in sync.
- **DB connection:** `db.get_db` is a per-request FastAPI dependency that yields a SQLAlchemy Core connection to `DATABASE_URL` (environment or `.env` in the service folder, real env var wins; default `sqlite:///registry.db`, relative paths resolved against the service folder; a bare `postgresql://` URL is rewritten to the psycopg driver). SQLite is opened with `mode=rw` and `PRAGMA foreign_keys` on. `mode=rw` is deliberate: a missing file must give 503 rather than a new empty DB. Writes must call `db.commit()`. List endpoints sort in Python (codepoint order, same as SQLite BINARY) so both databases return the same order.
- **Errors all go through `problems.py`.** Routes raise `ProblemError(status, detail)`; `problems.install(app)` also converts `RequestValidationError`, Starlette `HTTPException` (404/405), and SQLAlchemy `DBAPIError` (via `db_errors.is_unavailable`: file missing, Postgres unreachable, or tables missing) into RFC 9457 `application/problem+json`. The `code` is derived from the status (`422`/`405` → `VALIDATION`, `404` → `NOT_FOUND`, `409` → `CONFLICT`, `503` → `UNAVAILABLE`, plus `Retry-After`). The 422 title is pinned to "Unprocessable Entity" because Python 3.13+ renamed it.
- **Validation is split in two.** Field rules (positive areas/spacings, lat/lon bounds, `YYYY-MM-DD` and not-future planting date, `extra="forbid"`) live in `models.py`. Catalogue and farm existence checks are done in `plots.py` against the DB and return 422 `Unknown <thing>`. Duplicate plot names are detected by catching `sqlalchemy.exc.IntegrityError` and checking `db_errors.is_unique_violation`, giving 409.
- **PATCH semantics:** `*Patch` models subclass `models.Patch`; every field is optional but explicit `null` is rejected, and `.changes()` returns only the fields that were sent.
- **Catalogue routes** are generated in a loop from the `CATALOGUES` dict in `catalogue.py`. Only GET is registered, which is what makes other methods return 405.
- **Tests:** the `client` fixture in `tests/conftest.py` runs `seed_registry.sh` into a temp dir and points `DATABASE_URL` at it; with `TEST_POSTGRES_URL` set it runs against that Postgres instead (dropping schema `public` first). Seed IDs (`DEMO_FARM`, `EAST_FARM`, `NORTH_BLOCK`) are constants there. Use `assert_problem()` to check error responses.

## Project constraints

- The spec (P1 registry API task) says to implement only the listed functionality. Don't add endpoints, fields, or features it doesn't ask for; responses return only the spec'd fields.
- `docs/judgment-log.md` records the spec ambiguities and what the agent suggested. The "Decided"/"Why" entries are the user's to write, so don't fill them in.
- `.python-version` says 3.12, but the local `.venv` has been seen running 3.14; code must work on both.
- `.mcp.json` connects to PyCharm's MCP server on a local port that can change when PyCharm restarts.
