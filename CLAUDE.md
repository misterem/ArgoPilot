# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AgroPilot helps growers manage crops. Services live under `services/`, each its own uv project with its own `.venv`, `.env` and `config.py`; they never import each other's code and talk over HTTP only.

- `registry-service` (port 8000; FastAPI + SQLAlchemy Core on SQLite or PostgreSQL): farms, plots, and read-only crop/soil/emitter catalogues.
- `weather-service` (port 8001; async FastAPI + httpx): daily ET0 and rain from Open-Meteo, cached in memory per 0.1° grid cell.

## Commands

### registry-service

Run from `services/registry-service` (uv project, `package = false`):

```bash
uv sync                                   # install, including dev group (pytest, httpx)
cp .env.example .env                      # DATABASE_URL is required (no default); example uses SQLite
bash seed_registry.sh                     # recreate registry.db from scratch (needs the sqlite3 CLI)
uv run python scripts/setup_db.py         # new empty DB (e.g. Postgres): schema + the 15 seed rows, refuses if tables exist
uv run uvicorn main:app --host 127.0.0.1 --port 8000
uv run pytest                             # all tests
uv run pytest tests/test_plots.py::test_patch_changes_only_sent_fields   # one test
uv run pytest -k duplicate                # by name
# Postgres run: docker run --rm -d --name registry-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16
TEST_POSTGRES_URL=postgresql://postgres:pg@127.0.0.1:55432/postgres uv run pytest   # DROPs schema public before every test: throwaway DB only
uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --seconds 60   # NFR p95 check
```

### weather-service

Run from `services/weather-service`:

```bash
uv sync
cp .env.example .env                      # all 8 variables required; example uses free Open-Meteo
uv run uvicorn main:app --host 127.0.0.1 --port 8001
uv run pytest                             # no network: provider faked with httpx.MockTransport
uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8001 --seconds 60   # NFR-2.3, warms cache first
```

There is no linter or formatter configured.

## Architecture (registry-service)

- **Flat modules, imported by bare name** (`import farms`, `from db import get_db`). There is no package; `pyproject.toml` sets pytest `pythonpath = ["."]`, and uvicorn must be started from the service folder.
- **`schema.sql` owns the schema**, shared by SQLite and PostgreSQL (with `catalogue.sql` and `demo.sql`; `seed_registry.sh` pipes them into the `sqlite3` CLI, and `schema.py` loads them for `scripts/setup_db.py` and the tests). No migrations or ORM models: the tables, the `UNIQUE (farm_id, name)` on plots, and the foreign keys come from that file, and the code uses plain SQL through SQLAlchemy Core against them. A schema change means editing `schema.sql` and the matching pydantic models in `models.py`. SQL column lists are built from the response models' fields (`Plot.model_fields`), so the two must stay in sync.
- **DB connection:** `db.get_db` is a per-request FastAPI dependency that yields a SQLAlchemy Core connection to `DATABASE_URL`, read by `config.py` (pydantic-settings; environment or `.env` in the service folder, real env var wins; required, no default: `main.py` and `setup_db.py` exit with a clear message when it is missing or empty; relative SQLite paths resolved against the service folder; a bare `postgresql://` URL is rewritten to the psycopg driver). SQLite is opened with `mode=rw` and `PRAGMA foreign_keys` on. `mode=rw` is deliberate: a missing file must give 503 rather than a new empty DB. Writes must call `db.commit()`. List endpoints sort in Python (codepoint order, same as SQLite BINARY) so both databases return the same order.
- **Errors all go through `problems.py`.** Routes raise `ProblemError(status, detail)`; `problems.install(app)` also converts `RequestValidationError`, Starlette `HTTPException` (404/405), and SQLAlchemy `DBAPIError` (via `db_errors.is_unavailable`: file missing, Postgres unreachable, or tables missing) into RFC 9457 `application/problem+json`. The `code` is derived from the status (`422`/`405` → `VALIDATION`, `404` → `NOT_FOUND`, `409` → `CONFLICT`, `503` → `UNAVAILABLE`, plus `Retry-After`). The 422 title is pinned to "Unprocessable Entity" because Python 3.13+ renamed it.
- **Validation is split in two.** Field rules (positive areas/spacings, lat/lon bounds, `YYYY-MM-DD` and not-future planting date, `extra="forbid"`) live in `models.py`. Catalogue and farm existence checks are done in `plots.py` against the DB and return 422 `Unknown <thing>`. Duplicate plot names are detected by catching `sqlalchemy.exc.IntegrityError` and checking `db_errors.is_unique_violation`, giving 409.
- **PATCH semantics:** `*Patch` models subclass `models.Patch`; every field is optional but explicit `null` is rejected, and `.changes()` returns only the fields that were sent.
- **Catalogue routes** are generated in a loop from the `CATALOGUES` dict in `catalogue.py`. Only GET is registered, which is what makes other methods return 405.
- **Tests:** the `client` fixture in `tests/conftest.py` runs `seed_registry.sh` into a temp dir and points `DATABASE_URL` at it; with `TEST_POSTGRES_URL` set it runs against that Postgres instead (dropping schema `public` first). Seed IDs (`DEMO_FARM`, `EAST_FARM`, `NORTH_BLOCK`) are constants there. Use `assert_problem()` to check error responses. `conftest.py` sets a placeholder `DATABASE_URL` before importing `main` (which exits without one) and clears the cached settings (`config.get_settings.cache_clear()`) around every test.

## Architecture (weather-service)

- **Flat modules**, same conventions as registry-service (`config.py` with required settings and a startup exit, `problems.py` copied, not imported).
- **`provider.py` is the only module that knows Open-Meteo** (URL params, `et0_fao_evapotranspiration`, `precipitation_sum`, `utc_offset_seconds`). `fetch_daily` makes one call and raises `ProviderError` on anything short of a complete, valid 8-day answer (FR-2.8: never patch or default a day).
- **`forecast.py` holds every rule**: `cell_of` floors to 0.1° via `Decimal(repr(x))` (90/180 fold into the last cell); the provider is asked for the cell centre; `Forecaster.get` serves fresh entries without locking, otherwise runs or joins the cell's single in-flight cycle (1 + `PROVIDER_RETRIES` attempts), then answers fresh, stale (≤ `FORECAST_MAX_STALE_HOURS`, still covering local today…today+days−1), or raises `Unavailable` → 503. No memory of failures (user's choice: closest to FR-2.6).
- **`main.py`**: lifespan owns one `httpx.AsyncClient` and the `Forecaster` on `app.state`; routes get it through the `get_forecaster` dependency, which tests override.
- **Tests:** `tests/conftest.py` overwrites all 8 env vars before importing `main`; `tests/fakes.py` has `good_body()` (8 days from 2026-11-17, offset +7200) and MockTransport helpers; forecast tests inject a fake fetch, clock and sleep.

## Project constraints

- The specs (P1 registry API task, P2 task brief) say to implement only the listed functionality. Don't add endpoints, fields, or features it doesn't ask for; responses return only the spec'd fields.
- `docs/judgment-log.md` records the spec ambiguities and what the agent suggested. The "Decided"/"Why" entries are the user's to write, so don't fill them in.
- `.python-version` says 3.12, but the local `.venv` has been seen running 3.14; code must work on both.
- `.mcp.json` connects to PyCharm's MCP server on a local port that can change when PyCharm restarts.
