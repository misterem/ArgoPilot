# Postgres Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** registry-service runs on SQLite locally and in tests, and on PostgreSQL in production. `DATABASE_URL` (from the environment or `.env`) picks which one, and clients see no difference in behaviour.

**Architecture:** SQLAlchemy Core replaces raw `sqlite3`. The routes keep their hand-written SQL, wrapped in `text()`. One `schema.sql` serves both databases. Database errors are classified in one dependency-free module, so both `db.py` and `problems.py` can use it without a circular import.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 Core, psycopg 3, python-dotenv, pytest, Docker `postgres:16` for the opt-in Postgres run.

**Spec:** `docs/superpowers/specs/2026-11-16-postgres-support-design.md`

All paths below are relative to `services/registry-service/`, and all commands run from there.

## Global Constraints

- Every existing endpoint keeps the same status codes, the same problem+json bodies and `code`s, and `Retry-After` on every 503.
- Python 3.12 and 3.14 both work. Modules are flat and imported by bare name.
- `DATABASE_URL` defaults to `sqlite:///registry.db`. A real env var beats `.env` (`override=False`).
- SQLite is opened with `mode=rw&uri=true`, so the app never creates the file.
- Postgres URLs use the `postgresql+psycopg` driver. A bare `postgresql://` gets rewritten to it. Engine options are `pool_pre_ping=True` and `connect_args={"connect_timeout": 3}`.
- Column types: `TEXT` ids and `planting_date`, `DOUBLE PRECISION` for every former `REAL`, `INTEGER` for `available_water_mm_per_m`.
- Production setup loads `schema.sql` + `catalogue.sql` only (never `demo.sql`), and refuses to run if any of the tables already exist.
- No new endpoints or fields. `docs/judgment-log.md` is not touched.
- Dependencies: `sqlalchemy~=2.0`, `psycopg[binary]~=3.2`, `python-dotenv~=1.0`.

## Review Focus

1. **Sort order of list endpoints.** Postgres sorts text by its locale, while SQLite sorts by codepoint, so `"Zebra"` vs `"apple"` comes out differently. Lists must keep SQLite's codepoint order on both databases. *(Not in the spec; this plan settles it by sorting in Python. Test in Task 3.)*
2. **Float values exact on Postgres.** Values like `flow_lph` 0.6 and `lat` 31.25 must come back unchanged. Test in Task 1 (schema) and Task 5 (Postgres run).
3. **Unreachable Postgres returns 503 quickly** (well under 5 s) and with `Retry-After`. Test in Task 3.
4. **Postgres database without tables returns 503**, not 500. Test in Task 5.
5. **A request that fails with an integrity error leaves no open or failed transaction behind** for the next request. Postgres would otherwise poison the pooled connection. Test in Task 5: a duplicate POST returns 409, then a GET returns 200.

---

### Task 1: Split the seed into shared SQL files

**Files:**
- Create: `schema.sql`, `catalogue.sql`, `demo.sql`
- Modify: `seed_registry.sh`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `schema.sql` (5 `CREATE TABLE`s, no PRAGMA), `catalogue.sql` (crops/soils/emitters `INSERT`s), `demo.sql` (farms + plots `INSERT`s). Each statement ends with `;` at end of line, and no `;` appears inside string literals (Task 2's splitter relies on this). `seed_registry.sh [path]` keeps the same usage and output.

- [ ] **Step 1: Write the failing test** in `tests/test_schema.py`:

```python
def test_schema_file_uses_double_precision():
    sql = (SERVICE_DIR / "schema.sql").read_text()
    assert "REAL" not in sql.replace("DOUBLE PRECISION", "")
    assert "UNIQUE (farm_id, name)" in sql

def test_seed_keeps_float_values(client):
    assert client.get("/v1/emitters/dripnet-pc-0.6").json()["flow_lph"] == 0.6
    assert client.get(f"/v1/plots/{NORTH_BLOCK}").json()["lat"] == 31.25
```

- [ ] **Step 2:** Run `uv run pytest tests/test_schema.py -v`. Expected: FAIL (`schema.sql` doesn't exist).
- [ ] **Step 3:** Move the DDL and rows out of the heredoc into the three files, switching `REAL` to `DOUBLE PRECISION`. `seed_registry.sh` finds the files next to itself (`here="$(cd "$(dirname "$0")" && pwd)"`) and pipes `PRAGMA foreign_keys = ON;` followed by the three files into `sqlite3 "$db"`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass (84 existing + 2 new).
- [ ] **Step 5: Commit** — `git add schema.sql catalogue.sql demo.sql seed_registry.sh tests/test_schema.py && git commit -m "refactor: split registry seed into shared SQL files"`

### Task 2: Configuration, engine, and error classification (not yet wired in)

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (via `uv add sqlalchemy~=2.0 "psycopg[binary]~=3.2" python-dotenv~=1.0`)
- Create: `db_errors.py`, `schema.py`, `.env.example`
- Modify: `db.py` (add the functions below; keep the existing `get_db`/`exists` until Task 3)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces in `db.py`:
  - `SERVICE_DIR: Path`
  - `load_env(path: Path = SERVICE_DIR / ".env") -> None`, which calls `load_dotenv(path, override=False)`. It is called once at import.
  - `database_url() -> str`, which reads `DATABASE_URL` on every call and defaults to `"sqlite:///registry.db"`.
  - `engine_url(url: str) -> sqlalchemy.URL`:
    - SQLite: `database=f"file:{abs_path}"`, `query={"mode": "rw", "uri": "true"}`. A relative path resolves against `SERVICE_DIR`.
    - `postgresql://` and `postgres://` become the `postgresql+psycopg` driver.
    - Anything else is returned unchanged.
  - `get_engine(url: str) -> Engine`, cached per URL with `functools.cache`:
    - SQLite: `poolclass=NullPool` (opens per request, like today), `connect_args={"check_same_thread": False}`, and a `"connect"` event that runs `PRAGMA foreign_keys = ON`.
    - Postgres: `pool_pre_ping=True`, `connect_args={"connect_timeout": 3}`.
- Produces in `db_errors.py` (imports only SQLAlchemy):
  - `is_unique_violation(exc: IntegrityError) -> bool`: true when `exc.orig.sqlstate == "23505"`, or when `"UNIQUE" in str(exc.orig)`.
  - `is_unavailable(exc: DBAPIError) -> bool`: true for `OperationalError`, for `InterfaceError`, when `exc.connection_invalidated` is set, and for a `ProgrammingError` whose `orig.sqlstate == "42P01"`. False otherwise.
- Produces in `schema.py`:
  - `TABLES = ("farms", "crops", "soils", "emitters", "plots")`
  - `statements(filename: str) -> list[str]`: reads the file from `SERVICE_DIR`, splits on `;`, and drops blank pieces.
  - `existing_tables(conn: Connection) -> list[str]`: `sqlalchemy.inspect(conn).get_table_names()` ∩ `TABLES`, sorted.
  - `load(conn: Connection, *filenames: str) -> None`: runs `conn.exec_driver_sql()` for each statement.
- `.env.example` contains `# DATABASE_URL=sqlite:///registry.db` and `# DATABASE_URL=postgresql://user:password@host:5432/registry`.

- [ ] **Step 1: Write the failing tests** in `tests/test_config.py`:

```python
def test_default_url_is_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.database_url() == "sqlite:///registry.db"

def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    db.load_env(tmp_path / ".env")
    assert db.database_url() == "sqlite:///from-file.db"

def test_real_env_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///from-env.db")
    (tmp_path / ".env").write_text("DATABASE_URL=sqlite:///from-file.db\n")
    db.load_env(tmp_path / ".env")
    assert db.database_url() == "sqlite:///from-env.db"

def test_relative_sqlite_path_resolves_to_service_dir():
    url = db.engine_url("sqlite:///registry.db")
    assert url.database == f"file:{db.SERVICE_DIR / 'registry.db'}"
    assert url.query == {"mode": "rw", "uri": "true"}

def test_bare_postgres_url_gets_psycopg_driver():
    assert db.engine_url("postgresql://u:p@h:5432/d").drivername == "postgresql+psycopg"

def test_statements_split_schema():
    assert len(schema.statements("schema.sql")) == 5
```

Also add `test_is_unavailable_classification`, which builds fake `DBAPIError`s with `orig` objects carrying `sqlstate` `"42P01"` (expect true), `"42601"` (expect false), and `"23505"` (expect `is_unique_violation` true).

- [ ] **Step 2:** Run `uv run pytest tests/test_config.py -v`. Expected: FAIL (ImportError / AttributeError).
- [ ] **Step 3:** Implement the interfaces above.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** — `git add pyproject.toml uv.lock db.py db_errors.py schema.py .env.example tests/test_config.py && git commit -m "feat: DATABASE_URL config, SQLAlchemy engines, db error classification"`

### Task 3: Run the routes on SQLAlchemy

**Files:**
- Modify: `db.py` (`get_db`, `exists`; remove `REGISTRY_DB`, `db_path`, `DEFAULT_DB_PATH`)
- Modify: `farms.py`, `plots.py`, `catalogue.py`, `problems.py`
- Modify: `tests/conftest.py`, `tests/test_errors.py`, `tests/test_farms.py` (`REGISTRY_DB` → `DATABASE_URL=sqlite:///<path>`)
- Test: `tests/test_errors.py`, `tests/test_farms.py`, `tests/test_plots.py`

**Interfaces:**
- Consumes: `database_url`, `get_engine`, `is_unique_violation`, `is_unavailable` (Task 2).
- Produces:
  - `get_db() -> Iterator[sqlalchemy.Connection]`: `get_engine(database_url()).connect()`. An `OperationalError` there raises `ProblemError(503, "Database unavailable")`. The connection is always closed (closing rolls back anything uncommitted).
  - `exists(db: Connection, table: str, row_id: str) -> bool`.
  - Every route's `Db` alias becomes `Annotated[Connection, Depends(get_db)]`.
- Transaction rule: a write is `db.execute(...)` followed by `db.commit()`. No `with db.begin()`, because SQLAlchemy has already auto-begun after the earlier reads in the same request.
- SQL rules:
  - `text()` with `:name` params everywhere (positional `?` goes away).
  - Rows are read with `.mappings()`.
  - Farm area uses `COALESCE(SUM(area_m2), 0.0)`.
  - Lists sort in Python by codepoint, not with SQL `ORDER BY`: farms by `name`, plots by `(farm_id, name)` (or by `name` when filtered), catalogues by `id`.
- `problems.install`: replace the `sqlite3.OperationalError` handler with one for `sqlalchemy.exc.DBAPIError`. It returns `problem(503, "Database unavailable")` when `is_unavailable(exc)`, and otherwise re-raises (500).
- `plots._write` catches `sqlalchemy.exc.IntegrityError` and returns 409 when `is_unique_violation`. `farms.delete_farm` catches `sqlalchemy.exc.IntegrityError` and returns 409, as today.

- [ ] **Step 1: Write the failing tests**
  - In `tests/test_farms.py`:

  ```python
  def test_list_is_codepoint_ordered(client):
      for name in ("apple farm", "Zebra farm"):
          client.post("/v1/farms", json={"name": name})
      names = [f["name"] for f in client.get("/v1/farms").json()]
      assert names == sorted(names)
      assert names.index("Zebra farm") < names.index("apple farm")
  ```

  - In `tests/test_errors.py`:

  ```python
  def test_unreachable_postgres_is_unavailable_quickly(client, monkeypatch):
      monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")
      start = time.monotonic()
      response = client.get("/v1/farms")
      assert time.monotonic() - start < 5
      assert_problem(response, 503, "UNAVAILABLE")
      assert response.headers["retry-after"].isdigit()
  ```

  - Switch the three existing `REGISTRY_DB` monkeypatches and the `client` fixture to `monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")`.

- [ ] **Step 2:** Run `uv run pytest -q`. Expected: FAIL. The suite still reads `REGISTRY_DB`, so the fixture's database is ignored, and the Postgres test returns 500 or a non-problem response.
- [ ] **Step 3:** Implement the interfaces above in `db.py`, `problems.py`, `farms.py`, `plots.py`, `catalogue.py`. Load the `registry-api` skill first. Remove every `import sqlite3` from the routes and from `problems.py`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass, including `test_missing_database_is_unavailable` (no file is created) and `test_broken_database_is_unavailable`.
- [ ] **Step 5:** Smoke check. Run `bash seed_registry.sh && uv run uvicorn main:app --port 8000`, then `curl -s localhost:8000/v1/farms/b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001/area`. Expected: `{"area_m2":1800.0}`. Stop the server.
- [ ] **Step 6: Commit** — `git add db.py farms.py plots.py catalogue.py problems.py tests/ && git commit -m "feat: run registry routes on SQLAlchemy Core"`

### Task 4: Postgres setup script

**Files:**
- Create: `scripts/setup_db.py`
- Test: `tests/test_setup_db.py`

**Interfaces:**
- Consumes: `db.database_url`, `db.get_engine`, `schema.existing_tables`, `schema.load`.
- Produces: `main(url: str | None = None) -> int` (exit code), run as `uv run python scripts/setup_db.py`.
  - It inserts `SERVICE_DIR` into `sys.path` so the flat modules import.
  - Inside one `engine.begin()`: if `existing_tables(conn)` is non-empty, it prints `Tables already exist: <names>. Nothing changed.` to stderr and returns 1. Otherwise it runs `load(conn, "schema.sql", "catalogue.sql")`, prints `Created 5 tables and loaded 2 crops, 3 soils, 4 emitters.`, and returns 0.

- [ ] **Step 1: Write the failing tests** in `tests/test_setup_db.py`. Use SQLite files: `touch` an empty file so `mode=rw` can open it. Load the script with `runpy`/`importlib` from `scripts/setup_db.py`.

```python
def test_setup_loads_schema_and_catalogue_only(tmp_path):
    path = tmp_path / "new.db"; path.touch()
    assert setup_db.main(f"sqlite:///{path}") == 0
    with db.get_engine(f"sqlite:///{path}").connect() as conn:
        assert schema.existing_tables(conn) == sorted(schema.TABLES)
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM emitters").scalar() == 4
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM farms").scalar() == 0

def test_setup_refuses_when_tables_exist(tmp_path, capsys):
    path = tmp_path / "seeded.db"
    subprocess.run(["bash", str(SERVICE_DIR / "seed_registry.sh"), str(path)], check=True, capture_output=True)
    assert setup_db.main(f"sqlite:///{path}") == 1
    assert "Nothing changed" in capsys.readouterr().err
```

- [ ] **Step 2:** Run `uv run pytest tests/test_setup_db.py -v`. Expected: FAIL (the script doesn't exist).
- [ ] **Step 3:** Implement `scripts/setup_db.py` as specified.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** — `git add scripts/setup_db.py tests/test_setup_db.py && git commit -m "feat: non-destructive database setup script"`

### Task 5: Opt-in test run against Postgres

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_postgres.py`

**Interfaces:**
- Consumes: `schema.load`, `db.get_engine`, `db.engine_url`.
- Produces:
  - `BACKENDS = ["sqlite"] + (["postgres"] if os.environ.get("TEST_POSTGRES_URL") else [])`.
  - The `client` fixture is parametrized over `BACKENDS`. For Postgres it runs `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, then `load(conn, "schema.sql", "catalogue.sql", "demo.sql")` in one `engine.begin()`, then sets `DATABASE_URL` to `TEST_POSTGRES_URL`.
  - `requires_postgres = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="set TEST_POSTGRES_URL")`.

- [ ] **Step 1: Write the tests** in `tests/test_postgres.py`, all marked `requires_postgres`:

```python
def test_missing_tables_is_unavailable(client):
    with db.get_engine(os.environ["TEST_POSTGRES_URL"]).begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    response = client.get("/v1/plots")
    assert_problem(response, 503, "UNAVAILABLE")
    assert "retry-after" in response.headers

def test_connection_is_clean_after_conflict(client, plot_body):
    assert client.post("/v1/plots", json=plot_body).status_code == 201
    assert_problem(client.post("/v1/plots", json=plot_body), 409, "CONFLICT")
    assert client.get("/v1/plots").status_code == 200
```

These must use the Postgres-backed client only: request the `client` fixture indirectly with `"postgres"`.

- [ ] **Step 2:** Start Postgres: `docker run --rm -d --name registry-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:16`. Wait until `docker exec registry-pg pg_isready` reports `accepting connections`.
- [ ] **Step 3:** Run `TEST_POSTGRES_URL=postgresql://postgres:pg@127.0.0.1:55432/postgres uv run pytest -q`. Expected: every existing test passes on both `[sqlite]` and `[postgres]`, plus the new tests. Fix any Postgres-only failures in the owning module (most likely `problems.py`, `db_errors.py`, or the SQL in the routes) without changing the SQLite results.
- [ ] **Step 4:** Run `uv run pytest -q` without the variable. Expected: all pass, and the Postgres tests are skipped.
- [ ] **Step 5:** `docker stop registry-pg`.
- [ ] **Step 6: Commit** — `git add tests/ && git commit -m "test: run the suite against Postgres when TEST_POSTGRES_URL is set"`

### Task 6: Docs

**Files:**
- Modify: `README.md`, `../../CLAUDE.md`

- [ ] **Step 1:** Update the README:
  - Configuration with `DATABASE_URL` / `.env`, pointing at `.env.example`. Drop `REGISTRY_DB`.
  - Postgres setup: `uv run python scripts/setup_db.py`. It refuses to run on a database that already has tables.
  - The Postgres test run, using the Task 5 docker command.
  - The 503 row: "database missing, unreachable, or without tables".
  - The code layout: add `db_errors.py`, `schema.py`, `schema.sql`/`catalogue.sql`/`demo.sql`.
- [ ] **Step 2:** Update CLAUDE.md:
  - Commands: `setup_db.py` and the Postgres test run.
  - The "seed script owns the schema" bullet: it's now `schema.sql`, shared by both databases.
  - The DB connection bullet: `DATABASE_URL`, SQLAlchemy Core, `mode=rw`, writes call `db.commit()`, lists sort in Python.
  - The tests bullet: `DATABASE_URL`, `TEST_POSTGRES_URL`.
- [ ] **Step 3:** Run `grep -rn REGISTRY_DB --exclude-dir=.venv . ../../CLAUDE.md`. Expected: no output.
- [ ] **Step 4: Commit** — `git add README.md ../../CLAUDE.md && git commit -m "docs: DATABASE_URL, Postgres setup and test run"`
