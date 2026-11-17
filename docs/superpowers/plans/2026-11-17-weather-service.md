# weather-service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new FastAPI service on port 8001 that serves `GET /v1/forecast?lat&lon&days` from Open-Meteo, with a per-0.1°-cell in-memory cache, retries, stale fallback, and never an invented number.

**Architecture:** Flat modules like registry-service. `provider.py` makes one validated Open-Meteo call; `forecast.py` owns grid cells, the cache, freshness/stale/too-old rules, retries and single-flight per cell; `main.py` wires them into routes with problem+json errors.

**Tech Stack:** Python 3.12/3.14, uv (`package = false`), FastAPI, httpx (`AsyncClient`, `MockTransport` in tests), pydantic-settings, pytest with the anyio plugin.

**Spec:** `docs/superpowers/specs/2026-11-17-weather-service-design.md`

All paths below are relative to `services/weather-service` unless they start with `docs/` or `CLAUDE.md`. Work on branch `p2`.

## Global Constraints

- Services never import each other's code (`problems.py` is copied from registry-service, not imported).
- Settings via pydantic-settings in one `config.py`; `.env.example` committed with every variable; `.env` never committed; a missing required variable stops startup with a clear message.
- All 8 variables required: `PROVIDER_BASE_URL`, `PROVIDER_API_KEY` (present, may be empty), `PROVIDER_TIMEOUT_S`, `PROVIDER_RETRIES`, `PROVIDER_RETRY_BACKOFF_S`, `FORECAST_FRESH_HOURS`, `FORECAST_MAX_STALE_HOURS`, `RETRY_AFTER_S`.
- Open-Meteo field names (`et0_fao_evapotranspiration`, `precipitation_sum`, `daily`, `time`, `utc_offset_seconds`) appear only in `provider.py` (and its tests).
- FR-2.8: never a number the provider didn't give; a response with any bad day is rejected whole.
- No network in tests.
- Errors are RFC 9457 `application/problem+json` with `type`, `title`, `status`, `detail`, `code`; `422 VALIDATION`, `404 NOT_FOUND`, `503 UNAVAILABLE` + `Retry-After`.

## Review Focus

1. **Poles and antimeridian** (`lat=90`, `lat=-90`, `lon=180`, `lon=-180`): the provider is asked for a valid coordinate, never 90.05 or 180.05. Test: `test_cell_edges` (Task 3).
2. **Negative coordinates** floor toward −∞: `lat=-31.25` is in cell −31.3 (centre −31.25), not −31.2. Test: `test_cell_negative` (Task 3).
3. **A forecast fetched before local midnight, asked for just after** (still inside 3 h): first day is the new local today, 7 days still returned. Test: `test_after_local_midnight_today_is_first` (Task 3).
4. **Provider 200 with a single `null`**: rejected whole, never served as 0. Test: `test_null_value_is_failure` (Task 2).
5. **Concurrent requests while the provider is down**: one cycle (3 attempts total), all get the same outcome quickly. Test: `test_concurrent_requests_share_one_failed_cycle` (Task 3).

---

### Task 1: Service skeleton: config, problems, health

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `.python-version` (`3.12`), `.env.example`, `config.py`, `problems.py`, `main.py`, `tests/conftest.py`, `tests/test_app.py`

**Interfaces:**
- Produces:
  - `config.SERVICE_DIR`, `config.ENV_FILE`, `config.ConfigError`, `config.Settings` with fields `provider_base_url: str (min_length=1)`, `provider_api_key: str` (required, may be ""), `provider_timeout_s: float (>0)`, `provider_retries: int (>=0)`, `provider_retry_backoff_s: float (>=0)`, `forecast_fresh_hours: float (>0)`, `forecast_max_stale_hours: float (>0)`, `retry_after_s: int (>0)`; `config.load_settings(env_file: Path | None) -> Settings`; `config.get_settings() -> Settings` (`functools.cache`, reads `ENV_FILE` global at call time). Same pattern and message shape as `services/registry-service/config.py`: `"<NAMES> is/are not set. Copy .env.example to .env in services/weather-service, or set it in the environment."` — a field that fails a constraint (e.g. `PROVIDER_RETRIES=-1`) gives `"<NAME> is invalid: <pydantic msg>"`.
  - `problems.ProblemError(status: int, detail: str, headers: dict[str, str] | None = None)`, `problems.install(app)`; copy registry's file minus the SQLAlchemy handler and the `RETRY_AFTER_SECONDS` constant (503 headers are passed by the caller).
  - `main.app`; `GET /health -> {"status": "ok"}`; at import, `config.get_settings()` inside `try`, `sys.exit(f"weather-service: {exc}")` on `ConfigError`.
- Dependencies: `fastapi~=0.115.0`, `uvicorn~=0.32.0`, `httpx>=0.28`, `pydantic-settings~=2.6`; dev group `pytest>=9`. Pytest config as registry (`pythonpath = ["."]`, `testpaths = ["tests"]`).

- [ ] **Step 1: `uv init --bare`, add deps, write `.env.example`**

```
PROVIDER_BASE_URL=https://api.open-meteo.com
# Free tier needs no key; keep the variable (empty) so a paid plan is a config change.
PROVIDER_API_KEY=
PROVIDER_TIMEOUT_S=5
PROVIDER_RETRIES=2
PROVIDER_RETRY_BACKOFF_S=0.5
FORECAST_FRESH_HOURS=3
FORECAST_MAX_STALE_HOURS=24
RETRY_AFTER_S=60
```

- [ ] **Step 2: Failing tests** (`tests/conftest.py` sets every variable in `os.environ` to the `.env.example` values before importing `main`, overwriting the shell; autouse fixture clears `config.get_settings` cache)

```python
def test_health(client): assert client.get("/health").json() == {"status": "ok"}

def test_unknown_route_is_problem(client):
    r = client.get("/nope"); assert_problem(r, 404, "NOT_FOUND")

def test_missing_variable_is_named(tmp_path, monkeypatch):
    monkeypatch.delenv("PROVIDER_TIMEOUT_S")
    with pytest.raises(config.ConfigError, match="PROVIDER_TIMEOUT_S is not set"):
        config.load_settings(tmp_path / "absent.env")

def test_empty_api_key_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_API_KEY", "")
    assert config.load_settings(tmp_path / "absent.env").provider_api_key == ""

def test_api_key_must_be_present(tmp_path, monkeypatch):
    monkeypatch.delenv("PROVIDER_API_KEY")
    with pytest.raises(config.ConfigError, match="PROVIDER_API_KEY"):
        config.load_settings(tmp_path / "absent.env")

def test_invalid_value_is_named(tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER_RETRIES", "-1")
    with pytest.raises(config.ConfigError, match="PROVIDER_RETRIES is invalid"):
        config.load_settings(tmp_path / "absent.env")

def test_service_exits_at_startup_without_config(tmp_path):
    # subprocess `import config; config.ENV_FILE=<absent>; import main` with all 8 vars removed
    # → returncode != 0, "weather-service: " and "PROVIDER_BASE_URL" in stderr, no "Traceback"
```

`assert_problem(response, status, code)` in conftest, same as registry's.

- [ ] **Step 3: Run** `uv run pytest -q` → Expected: errors (`No module named 'config'`).
- [ ] **Step 4: Implement** `config.py`, `problems.py`, `main.py`.
- [ ] **Step 5: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 6: Commit** `feat(weather): service skeleton, config, problem errors, health`

### Task 2: `provider.py`: one validated Open-Meteo call

**Files:**
- Create: `provider.py`, `tests/test_provider.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Day: date: datetime.date; et0_mm: float; rain_mm: float`
  - `@dataclass(frozen=True) class ProviderForecast: days: tuple[Day, ...]; utc_offset_seconds: int`
  - `class ProviderError(Exception)` (message says what was wrong)
  - `FETCH_DAYS = 8`
  - `async def fetch_daily(client: httpx.AsyncClient, settings: Settings, lat: float, lon: float) -> ProviderForecast` — one attempt, no retry. GET `{provider_base_url}/v1/forecast` with `latitude`, `longitude`, `daily=et0_fao_evapotranspiration,precipitation_sum`, `timezone=auto`, `forecast_days=8`, plus `apikey` only when non-empty; `timeout=settings.provider_timeout_s`. Every failure (timeout/transport error, non-2xx, non-JSON, missing/extra-short/mismatched arrays, `null`, non-number incl. bool, unparseable date, non-consecutive dates, fewer than 8 days, missing `utc_offset_seconds`) raises `ProviderError`.

- [ ] **Step 1: Failing tests**, with a helper `transport(handler)` building `httpx.MockTransport` and a `good_body()` of 8 consecutive days from `2026-11-17`, `utc_offset_seconds: 7200`:

```python
async def test_parses_good_body():           # days[0] == Day(date(2026,11,17), 3.1, 0.0); len == 8; offset 7200
async def test_sends_expected_query():       # captured request: latitude/longitude as given, daily=..., timezone=auto, forecast_days=8, no apikey
async def test_sends_apikey_when_set():      # settings with provider_api_key="k" → apikey=k
async def test_timeout_is_failure():         # handler raises httpx.ReadTimeout → ProviderError
async def test_error_status_is_failure():    # 400 {"error": true, "reason": "x"} and 500 → ProviderError
async def test_non_json_is_failure():        # 200 "<html>" → ProviderError
async def test_missing_field_is_failure():   # parametrize: drop daily / time / et0 / precipitation / utc_offset_seconds
async def test_null_value_is_failure():      # one et0 null → ProviderError (never 0)
async def test_non_number_is_failure():      # "3.1" string, and true
async def test_mismatched_lengths_is_failure():
async def test_too_few_days_is_failure():    # 7 days
async def test_non_consecutive_dates_is_failure():
```

Mark async tests `@pytest.mark.anyio` and add `anyio_backend` fixture returning `"asyncio"` in conftest.

- [ ] **Step 2: Run** `uv run pytest tests/test_provider.py -q` → Expected: errors on `No module named 'provider'`.
- [ ] **Step 3: Implement** `provider.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Commit** `feat(weather): Open-Meteo client with strict validation`

### Task 3: `forecast.py`: cells, cache, retries, stale, single flight

**Files:**
- Create: `forecast.py`, `tests/test_forecast.py`

**Interfaces:**
- Consumes: `provider.Day`, `provider.ProviderForecast`, `provider.ProviderError`, `provider.FETCH_DAYS`.
- Produces:
  - `def cell_of(lat: float, lon: float) -> tuple[Decimal, Decimal]` — floor to 0.1° using `Decimal(repr(x))`; `lat == 90` → `89.9`, `lon == 180` → `179.9`.
  - `def cell_centre(cell: tuple[Decimal, Decimal]) -> tuple[float, float]` — cell + 0.05, as float.
  - `@dataclass(frozen=True) class Answer: days: tuple[Day, ...]; fetched_at: datetime; stale: bool`
  - `class Unavailable(Exception)`
  - `class Forecaster.__init__(self, fetch: Callable[[float, float], Awaitable[ProviderForecast]], settings: Settings, now: Callable[[], datetime] = <utc now>, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep)`
  - `async def Forecaster.get(self, lat: float, lon: float, days: int) -> Answer` — raises `Unavailable`.

Rules (from the spec; the implementer writes the code):
- Entry = `ProviderForecast` + `fetched_at`. Local today = `(now() + utc_offset_seconds).date()`. An entry *covers* `days` when it has every date `today … today+days−1`; the answer is exactly those days.
- Fresh (`now − fetched_at < fresh_hours`) and covers → answer, `stale=False`, no lock, no fetch.
- Otherwise single flight: if a cycle for the cell is in flight, await it (shielded); else start one. A cycle = up to `1 + provider_retries` calls to `fetch(*cell_centre(cell))`, `sleep(provider_retry_backoff_s)` between failed attempts; success stores the new entry. After the cycle (own or awaited): success → answer from the new entry, `stale=False` (if it somehow doesn't cover → `Unavailable`); failure → the existing entry if `now − fetched_at <= max_stale_hours` and it covers → `stale=True` with its original `fetched_at`; else `Unavailable`.
- No memory of failures: the next request after a finished failed cycle starts a new cycle.

- [ ] **Step 1: Failing tests** with a `FakeFetch` (records calls, returns queued results or raises `ProviderError`), a mutable clock, and a no-op `sleep`:

```python
def test_cell_same_cell():            assert cell_of(31.25, 34.79) == cell_of(31.29, 34.71) == (Decimal("31.2"), Decimal("34.7"))
def test_cell_boundary():             assert cell_of(31.3, 34.7)[0] == Decimal("31.3")
def test_cell_negative():             assert cell_of(-31.25, -0.01) == (Decimal("-31.3"), Decimal("-0.1"))
def test_cell_edges():                assert cell_centre(cell_of(90, 180)) == (89.95, 179.95); assert cell_centre(cell_of(-90, -180)) == (-89.95, -179.95)
async def test_first_request_fetches_cell_centre():     # fetch called with (31.25, 34.75); answer 7 days from 2026-11-17, stale False
async def test_fresh_hit_does_not_fetch():              # second get 2h59m later, nearby point same cell → 1 fetch total
async def test_after_fresh_window_refetches():          # 3h later → 2 fetches
async def test_days_slices_from_today():                # days=3 → 3 days
async def test_after_local_midnight_today_is_first():   # fetched 2026-11-17T21:30Z (offset +2h → local 23:30), ask at 22:30Z → first day 2026-11-18, 7 days, 1 fetch
async def test_retries_twice_then_succeeds():           # fail, fail, ok → 3 fetches, stale False, sleep called twice with 0.5
async def test_failure_serves_stale():                  # ok at t0; at t0+4h fail×3 → stale True, fetched_at == t0, numbers equal the t0 forecast
async def test_failure_without_entry_is_unavailable():  # fail×3 → Unavailable, 3 fetches
async def test_stale_older_than_24h_is_unavailable():   # ok at t0; at t0+24h+1s fail×3 → Unavailable
async def test_stale_at_exactly_24h_is_served():
async def test_failure_does_not_touch_entry():          # after a failed cycle, a later success-less request still serves the original
async def test_no_failure_memory():                     # fail×3, then immediately another get → 3 more fetches (6 total)
async def test_concurrent_requests_share_one_failed_cycle():   # 5 gets gathered while fetch blocks on an Event then fails → 3 fetches total, all 5 raise Unavailable
async def test_concurrent_requests_share_one_success():        # 5 gathered → 1 fetch, all 5 answers equal
async def test_fresh_hit_does_not_wait_for_inflight_other_cell():  # in-flight blocked fetch for cell A; get for fresh cell B returns
```

- [ ] **Step 2: Run** `uv run pytest tests/test_forecast.py -q` → Expected: errors on `No module named 'forecast'`.
- [ ] **Step 3: Implement** `forecast.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Commit** `feat(weather): forecast cache with retries, stale fallback and single flight`

### Task 4: `GET /v1/forecast` route

**Files:**
- Modify: `main.py`
- Create: `tests/test_forecast_api.py`

**Interfaces:**
- Consumes: `Forecaster`, `Answer`, `Unavailable` (Task 3); `provider.fetch_daily` (Task 2); `ProblemError` (Task 1).
- Produces: `main.get_forecaster(request: Request) -> Forecaster` (dependency returning `request.app.state.forecaster`; tests override it via `app.dependency_overrides`). Lifespan creates one `httpx.AsyncClient`, builds `Forecaster(fetch=lambda la, lo: provider.fetch_daily(client, settings, la, lo), settings=settings)`, closes the client on shutdown.
- Query: `lat: float` (−90…90), `lon: float` (−180…180), `days: int` (1…7), all required → 422 `VALIDATION` otherwise.
- 200 body: `{"lat", "lon"` (as sent), `"source": "open-meteo", "fetched_at": "YYYY-MM-DDTHH:MM:SSZ", "stale", "days": [{"date": "YYYY-MM-DD", "et0_mm", "rain_mm"}]}` — only these fields.
- `Unavailable` → `ProblemError(503, "Weather provider unavailable and no recent forecast for this location", {"Retry-After": str(settings.retry_after_s)})`.

- [ ] **Step 1: Failing tests** (override `get_forecaster` with a `Forecaster` built on `provider.fetch_daily` + `httpx.MockTransport` serving `good_body()` or failing, and a fixed clock):

```python
def test_forecast_shape(client):     # exact keys; lat/lon echo 31.25/34.79; 7 days; days[0] == {"date": "2026-11-17", "et0_mm": 3.1, "rain_mm": 0.0}; fetched_at endswith "Z"; stale False
def test_days_param(client):         # days=1 → 1 day
@pytest.mark.parametrize("query", ["lat=91&lon=0&days=7", "lat=-91&lon=0&days=7", "lat=0&lon=181&days=7",
    "lat=0&lon=-181&days=7", "lat=0&lon=0&days=0", "lat=0&lon=0&days=8", "lat=0&lon=0", "lat=abc&lon=0&days=7", "lat=nan&lon=0&days=7"])
def test_bad_query_is_422(client, query):   # assert_problem 422 VALIDATION
def test_bounds_are_inclusive(client):      # lat=90&lon=180&days=7 and lat=-90&lon=-180&days=1 → 200
def test_provider_down_no_cache_is_503(client_down):  # assert_problem 503 UNAVAILABLE; Retry-After == "60"
def test_provider_down_with_cache_is_stale(...)       # first call ok, advance clock 4h, provider down → 200 stale True, same numbers
```

- [ ] **Step 2: Run** `uv run pytest tests/test_forecast_api.py -q` → Expected: FAIL (404 on `/v1/forecast`).
- [ ] **Step 3: Implement** the route, lifespan and dependency in `main.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Live smoke** (one real Open-Meteo call): `cp .env.example .env`, `uv run uvicorn main:app --port 8001` (background), `curl "http://127.0.0.1:8001/v1/forecast?lat=31.25&lon=34.79&days=7"` → Expected: 200, 7 days starting today (local Israel date), `stale: false`, non-null numbers. Stop the server.
- [ ] **Step 6: Commit** `feat(weather): GET /v1/forecast`

### Task 5: Latency check, README, CLAUDE.md

**Files:**
- Create: `scripts/measure_latency.py`, `README.md`
- Modify: `CLAUDE.md` (repo root)

- [ ] **Step 1: `scripts/measure_latency.py`** — adapt registry's script: same fixed-schedule 10 rps loop and p50/p95/max table; paths are `/v1/forecast` for the 4 seed plot coordinates (31.25,34.79 / 31.26,34.80 / 31.40,34.60 / 31.41,34.61) with `days=7`; it sends one warm-up request per path first and excludes them, so every measured request is a fresh-cache hit.
- [ ] **Step 2: Measure** with the server running: `uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8001 --seconds 60` → Expected: p95 ≤ 100 ms overall and per path.
- [ ] **Step 3: `README.md`** — run steps (`uv sync`, `cp .env.example .env`, uvicorn on 8001); configuration table (8 variables, meaning, example); Open-Meteo variables and units (`et0_fao_evapotranspiration` mm/day FAO-56 Penman-Monteith grass reference → `et0_mm`; `precipitation_sum` mm/day rain + showers + snowfall → `rain_mm`, and why not `rain_sum`; `timezone=auto`; `forecast_days=8`); grid cells and cell-centre rule; fresh / stale / too-old rules with the 24 h choice and its why (from the spec); single flight and no failure memory, and the ~16 s worst case; API with the 200 example and error table; measured p95 with date; Mermaid `sequenceDiagram`: client → weather: GET; alt fresh → 200; else provider call, loop retries; alt success → 200 stale false; else entry ≤ 24 h → 200 stale true; else 503 + Retry-After; test command.
- [ ] **Step 4: `CLAUDE.md`** — intro lists `weather-service` (port 8001, Open-Meteo, in-memory cache); a "weather-service" commands block (`uv sync`, `cp .env.example .env`, uvicorn on 8001, `uv run pytest`, latency script); a short architecture section: flat modules, `provider.py` is the only place with Open-Meteo names, `forecast.py` rules, tests use `MockTransport` + fake clock, no network.
- [ ] **Step 5: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 6: Commit** `docs(weather): README, latency check, CLAUDE.md`
