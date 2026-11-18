# planner-service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI service on port 8002 serving `GET /v1/plots/{id}/plan?days=` — a day-by-day drip plan computed by a pure FAO-56 engine from registry-service and weather-service data.

**Architecture:** Flat modules like the other services. `crops.py` (FAO table) and `engine.py` (pure functions, no I/O) hold every number; `clients.py` calls registry and weather with one `httpx.AsyncClient` and validates their answers; `main.py` orders the calls and maps failures to problem+json. The method is also written into the `irrigation-calc-reference` skill (FR-2.11).

**Tech Stack:** Python 3.12/3.14, uv (`package = false`), FastAPI, httpx (`AsyncClient`, `MockTransport` in tests), pydantic-settings, pytest + anyio plugin.

**Spec:** `docs/superpowers/specs/2026-11-17-planner-service-design.md`

Paths are relative to `services/planner-service` unless they start with `docs/`, `.claude/` or `CLAUDE.md`. Branch `p2`.

## Global Constraints

- Services never import each other's code (`problems.py` is copied from weather-service and extended).
- `config.py` (pydantic-settings), all 4 variables required: `REGISTRY_URL`, `WEATHER_URL`, `REGISTRY_TIMEOUT_S` (example 5), `WEATHER_TIMEOUT_S` (example 20); clear startup exit naming a missing/invalid one; `.env.example` committed, `.env` never.
- Every number in the plan comes from `engine.py`; nothing is defaulted, zero-filled, or estimated when upstream data is missing (FR-2.8/2.14).
- Errors are RFC 9457 `application/problem+json` with `code`: `422 VALIDATION`, `404 NOT_FOUND`, `503 UPSTREAM_UNAVAILABLE` (detail starts with `registry-service unavailable` or `weather-service unavailable`).
- No network in tests. Python 3.12 and 3.14.

## Review Focus

1. **A value landing exactly on the threshold** (Dr_start + ETc == RAW, also with float noise like 48.99999999999) → no irrigation. Test: `test_exactly_at_threshold_does_not_irrigate` (Task 2).
2. **Season ends inside the window** → rows stop at `season_end`, never a zero row after it. Test: `test_truncates_at_season_end` (Task 2), `test_truncated_plan_response` (Task 4).
3. **A plot id with `/`, `..` or `?`** → percent-encoded into one path segment; registry says 404 → our 404, never a different registry route. Test: `test_plot_id_is_one_encoded_segment` (Task 3).
4. **Weather answers with a null, a missing day, or different dates than asked** → 503 `weather-service unavailable`, never a plan. Test: `test_bad_forecast_is_upstream_error` (Task 3).
5. **Weather `stale: true`** → every day `stale: true` and top-level `stale: true`, plan still computed. Test: `test_stale_forecast_marks_every_day` (Task 4).

---

### Task 1: Service skeleton: config, problems, health

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `.python-version` (`3.12`), `.env.example`, `config.py`, `problems.py`, `main.py`, `tests/conftest.py`, `tests/test_app.py`

**Interfaces:**
- Produces:
  - `config.Settings`: `registry_url: str (min_length=1)`, `weather_url: str (min_length=1)`, `registry_timeout_s: float (>0)`, `weather_timeout_s: float (>0)`; `config.load_settings(env_file)`, `config.get_settings()` (cached, reads `ENV_FILE` at call time), `config.ConfigError`, `config.SERVICE_DIR`, `config.ENV_FILE`. Same error-message logic as `services/weather-service/config.py` (missing → "X is not set", constraint → "X is invalid: …"), service name `planner-service`.
  - `problems.ProblemError(status: int, detail: str, headers: dict[str, str] | None = None, code: str | None = None)` — `code` overrides the status-derived code; `problems.install(app)`. Copy weather-service's file and add the `code` parameter through `problem()`.
  - `main.app`, `GET /health → {"status": "ok"}`, startup `sys.exit(f"planner-service: {exc}")` on `ConfigError`.
- Dependencies as weather-service: `fastapi~=0.115.0`, `uvicorn~=0.32.0`, `httpx>=0.28`, `pydantic-settings~=2.6`; dev `pytest>=9`.

- [ ] **Step 1: Scaffold + `.env.example`**

```
# All variables are required.
REGISTRY_URL=http://127.0.0.1:8000
WEATHER_URL=http://127.0.0.1:8001
REGISTRY_TIMEOUT_S=5
# Must exceed weather-service's worst case (~16 s: 3 attempts x 5 s + 2 x 0.5 s backoff).
WEATHER_TIMEOUT_S=20
```

- [ ] **Step 2: Failing tests** — conftest overwrites the 4 vars in `os.environ` before importing `main` (`REGISTRY_URL=http://registry.test`, `WEATHER_URL=http://weather.test`), autouse cache clear, `anyio_backend`, `client`, `assert_problem` (as weather-service). `tests/test_app.py`: `test_health`, `test_unknown_route_is_problem` (404 NOT_FOUND), `test_missing_variable_is_named` (`WEATHER_URL is not set`), `test_invalid_value_is_named` (`REGISTRY_TIMEOUT_S=0` → `REGISTRY_TIMEOUT_S is invalid`), `test_problem_code_override` (a throwaway route raising `ProblemError(503, "x", code="UPSTREAM_UNAVAILABLE")` → body code `UPSTREAM_UNAVAILABLE`), `test_service_exits_at_startup_without_config` (subprocess, as weather-service: non-zero, `planner-service: ` and `REGISTRY_URL` in stderr, no `Traceback`).
- [ ] **Step 3: Run** `uv run pytest -q` → Expected: `No module named 'config'`.
- [ ] **Step 4: Implement** `config.py`, `problems.py`, `main.py`.
- [ ] **Step 5: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 6: Commit** `feat(planner): service skeleton, config, problem errors, health`

### Task 2: `crops.py` + `engine.py` + skill method section

**Files:**
- Create: `crops.py`, `engine.py`, `tests/test_engine.py`
- Modify: `.claude/skills/irrigation-calc-reference/SKILL.md` (repo root)

**Interfaces:**
- Produces (`crops.py`): `@dataclass(frozen=True) class Crop: id: str; stages: tuple[int, int, int, int]; kc_ini: float; kc_mid: float; kc_end: float; root_depth_m: float; p: float` with `season_length` property (sum of stages); `CROPS: dict[str, Crop]` = `tomato` (30,40,45,30; 0.60/1.15/0.80; 0.7; 0.40), `bell-pepper` (30,35,40,20; 0.60/1.05/0.90; 0.5; 0.30), each with a comment citing FAO-56 Table 11/12/22 and the row used.
- Produces (`engine.py`):
  - `@dataclass(frozen=True) class Field: planting_date: date; area_m2: float; row_spacing_m: float; emitter_spacing_m: float; emitter_flow_lph: float; available_water_mm_per_m: float`
  - `@dataclass(frozen=True) class WeatherDay: date: date; et0_mm: float; rain_mm: float`
  - `@dataclass(frozen=True) class PlanDay: date; et0_mm; rain_mm; kc; etc_mm; irrigation_mm; litres: int; run_minutes: int; bucket_end_mm` (floats full precision except the two ints)
  - `@dataclass(frozen=True) class Plan: season_end: date; bucket_capacity_mm: float; threshold_mm: float; days: tuple[PlanDay, ...]`
  - `class SeasonError(Exception)` (message is the 422 detail)
  - `def kc_on_day(crop: Crop, i: int) -> float` (Eq. 66, 1-based i)
  - `def round_half_up(x: float, ndigits: int = 0) -> float` (via `Decimal(repr(x)).quantize(..., ROUND_HALF_UP)`)
  - `def make_plan(crop: Crop, field: Field, weather: Sequence[WeatherDay]) -> Plan`
  - `TOLERANCE_MM = 1e-9`
- Method: exactly the design's "The method" section — start `Dr = RAW`; per day ETc, effective rain (`rain >= 0.2 * et0`), `Dr_start = max(0, Dr_prev − P)`, irrigate `I = Dr_start + ETc − RAW` only if that is `> TOLERANCE_MM`, else `Dr_end = Dr_start + ETc` clamped to TAW; `litres = round_half_up(I × area)`, `run_minutes = round_half_up(I × area / (area / (row × emitter) × flow) × 60)` from the unrounded litres; `bucket_end_mm = TAW − Dr_end`; `threshold_mm = TAW − RAW`. Season: `i` from `weather[0].date`; `i > L` → `SeasonError("Season ended on <YYYY-MM-DD> (day L of L); update the planting date.")`; `i < 1` → `SeasonError("Season has not started (planting date <YYYY-MM-DD>).")`; rows with `i > L` dropped.

- [ ] **Step 1: Failing tests**

```python
TOMATO, PEPPER = CROPS["tomato"], CROPS["bell-pepper"]
TODAY = date(2026, 11, 17)
BASE = Field(TODAY - timedelta(days=99), 1000, 1.5, 0.4, 1.0, 175)   # today is day 100 (mid-season), loam
def field(**changes): return replace(BASE, **changes)
def days(*rows): return [WeatherDay(TODAY + timedelta(days=n), et0, rain) for n, (et0, rain) in enumerate(rows)]

def test_crop_table(): assert TOMATO.season_length == 145 and PEPPER.season_length == 125
def test_kc_curve_tomato():  # Eq. 66 on the table values
    assert kc_on_day(TOMATO, 10) == 0.6; assert kc_on_day(TOMATO, 100) == 1.15
    assert kc_on_day(TOMATO, 50) == pytest.approx(0.6 + 20/40 * 0.55)        # 0.875
    assert kc_on_day(TOMATO, 130) == pytest.approx(1.15 + 15/30 * (0.80 - 1.15))  # 0.975
def test_kc_curve_skill_case_1():  # skill Case 1 with its adjusted Kc mid/end
    crop = replace(TOMATO, kc_mid=1.2117, kc_end=0.8617)
    assert kc_on_day(crop, 50) == pytest.approx(0.9059, abs=1e-4); assert kc_on_day(crop, 130) == pytest.approx(1.0367, abs=1e-4)
def test_spec_example_248_minutes():
    plan = make_plan(TOMATO, field(), days((6.0, 0.0)))
    d = plan.days[0]
    assert (d.kc, d.etc_mm, d.irrigation_mm, d.litres, d.run_minutes) == (1.15, pytest.approx(6.9), pytest.approx(6.9), 6900, 248)
    assert plan.bucket_capacity_mm == pytest.approx(122.5) and plan.threshold_mm == pytest.approx(73.5)
    assert d.bucket_end_mm == pytest.approx(73.5)
def test_design_worked_case_three_days():
    plan = make_plan(TOMATO, field(), days((6.0, 0.0), (5.0, 12.0), (6.0, 0.5)))
    assert [(d.litres, d.run_minutes) for d in plan.days] == [(6900, 248), (0, 0), (650, 23)]
    assert [round(d.bucket_end_mm, 2) for d in plan.days] == [73.5, 79.75, 73.5]
    assert plan.days[1].irrigation_mm == 0 and plan.days[2].irrigation_mm == pytest.approx(0.65)
def test_small_rain_is_ignored():   # rain 1.0 < 0.2*6.0 → same as no rain: irrigates 6.9
def test_rain_at_threshold_counts(): # rain exactly 0.2*ET0 counts
def test_heavy_rain_drains_and_bucket_stays_full():  # rain 200 on day 1 → Dr_start 0, no irrigation, bucket_end = 122.5 − 6.9
def test_exactly_at_threshold_does_not_irrigate():   # day 1 rain chosen so Dr_start + ETc == RAW (e.g. ET0 5.0, Kc 1.15 → ETc 5.75; rain 5.75 ≥ 1.0) → irrigation 0
def test_float_noise_at_threshold_does_not_irrigate():  # rain = 5.75 + 1e-12 / − 1e-12 → irrigation_mm == 0 both
def test_pepper_bucket():   # PEPPER on sand (83) → TAW 41.5, RAW 12.45, threshold 29.05
def test_truncates_at_season_end():  # planting so today is day 144 of 145 → 2 rows, season_end == TODAY + 1 day
def test_season_ended_raises():      # today day 146 → SeasonError, message "Season ended on 2026-11-16 (day 145 of 145); update the planting date."
def test_planting_after_today_raises(): # planting TODAY + 1 → SeasonError "Season has not started (planting date 2026-11-18)."
def test_planting_day_is_day_one():     # planting TODAY → kc 0.6, 1 row ok
def test_run_longer_than_a_day_is_reported():  # row 2 m, emitter 1 m, flow 0.6 → run_minutes > 1440, not capped
def test_round_half_up(): assert round_half_up(23.5) == 24 and round_half_up(0.125, 2) == 0.13
```

- [ ] **Step 2: Run** `uv run pytest tests/test_engine.py -q` → Expected: `No module named 'crops'`.
- [ ] **Step 3: Implement** `crops.py`, `engine.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Skill section.** Append to `.claude/skills/irrigation-calc-reference/SKILL.md` a section `## AgroPilot planner method (what planner-service computes)`: the crop table, season rules (day 1 = planting day, refuse past season, truncate), start at `Dr = RAW`, the per-day order with the top-up rule and the 1e-9 tolerance, effective-rain rule, drip conversion and rounding, the >1440-minute note, and the worked case table (6900/248, 0/0, 650/23). Where the existing text marks a choice **open** (Kc end tomato, p constant vs adjusted, trigger timing, gross depth/run time, single vs dual), add "→ planner: <choice>, see AgroPilot planner method". Also change the "Common mistakes" bullet about I vs run time to say the planner's conversion has no efficiency factor by decision.
- [ ] **Step 6: Commit** `feat(planner): FAO-56 engine and crop table; skill gains the planner method`

### Task 3: `clients.py`: registry and weather calls

**Files:**
- Create: `clients.py`, `tests/test_clients.py`, `tests/fakes.py`

**Interfaces:**
- Consumes: `Settings` (Task 1); `engine.WeatherDay` (Task 2).
- Produces:
  - `class PlotNotFound(Exception)`; `class UpstreamUnavailable(Exception)` with `service: str` (`"registry-service"` / `"weather-service"`), `reason: str`, `retry_after: str | None`, and `detail` property `f"{service} unavailable: {reason}"`.
  - `@dataclass(frozen=True) class Plot: id: str; crop_id: str; planting_date: date; soil_id: str; emitter_id: str; area_m2: float; row_spacing_m: float; emitter_spacing_m: float; lat: float; lon: float`
  - `@dataclass(frozen=True) class Forecast: fetched_at: str; stale: bool; days: tuple[WeatherDay, ...]`
  - `async def get_plot(http, settings, plot_id: str) -> Plot` — `GET {registry_url}/v1/plots/{quote(plot_id, safe="")}`; 404 → `PlotNotFound`.
  - `async def get_soil_water(http, settings, soil_id: str) -> float` — `/v1/soils/{id}` → `available_water_mm_per_m` (> 0).
  - `async def get_emitter_flow(http, settings, emitter_id: str) -> float` — `/v1/emitters/{id}` → `flow_lph` (> 0).
  - `async def get_forecast(http, settings, lat: float, lon: float, days: int) -> Forecast` — `GET {weather_url}/v1/forecast?lat&lon&days`.
- Rules: timeouts per service from settings; any transport error/timeout, non-2xx (except plot 404), non-JSON, missing field, wrong type, non-positive area/spacing/flow/water, unparseable date → `UpstreamUnavailable(service, reason)`. Weather: exactly `days` entries, consecutive dates, each `et0_mm`/`rain_mm` finite ≥ 0 (bool rejected), `stale` a bool; a weather 503 passes its `Retry-After` header into `retry_after`.

- [ ] **Step 1: Failing tests** with `tests/fakes.py` (registry JSON for plot/soil/emitter matching registry's models; `forecast_body(start, days, stale=False, et0=..., rain=...)`; `MockTransport` router by path):

```python
async def test_get_plot_parses():                 # fields; planting_date is a date
async def test_plot_404_is_not_found():
async def test_plot_id_is_one_encoded_segment():  # plot_id "../farms?x" → request path "/v1/plots/..%2Ffarms%3Fx"; 404 → PlotNotFound
async def test_registry_500_is_upstream():        # UpstreamUnavailable, service "registry-service"
async def test_registry_timeout_is_upstream():    # handler raises httpx.ReadTimeout
async def test_registry_bad_body_is_upstream():   # non-JSON; missing flow_lph; flow_lph 0
async def test_soil_and_emitter():                # 175.0 and 1.0
async def test_get_forecast_parses():             # query lat/lon/days sent; 7 WeatherDays; stale/fetched_at kept
@pytest.mark.parametrize("problem", ["null_et0", "missing_day", "extra_day", "gap_in_dates", "negative_rain", "string_number", "no_stale"])
async def test_bad_forecast_is_upstream_error(problem):   # service "weather-service"
async def test_weather_503_keeps_retry_after():   # 503 with Retry-After: 60 → retry_after == "60"
async def test_weather_down_is_upstream():        # ConnectError
async def test_timeouts_come_from_settings():     # captured request.extensions["timeout"] read == 5 for registry, 20 for weather
```

- [ ] **Step 2: Run** `uv run pytest tests/test_clients.py -q` → Expected: `No module named 'clients'`.
- [ ] **Step 3: Implement** `clients.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Commit** `feat(planner): registry and weather clients with strict validation`

### Task 4: `GET /v1/plots/{id}/plan`

**Files:**
- Modify: `main.py`
- Create: `tests/test_plan_api.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: lifespan owning one `httpx.AsyncClient` on `app.state.http`; dependency `main.get_http(request) -> httpx.AsyncClient` (tests override it with a MockTransport client).
- Flow: validate `days` (`Query(7, ge=1, le=7)`) → `get_plot` (`PlotNotFound` → 404 `Plot not found`) → `asyncio.gather` soil, emitter, forecast(days) → first `UpstreamUnavailable` in order registry, weather → `ProblemError(503, exc.detail, {"Retry-After": exc.retry_after} if set, code="UPSTREAM_UNAVAILABLE")` → crop lookup (`422`, `No crop parameters for '<id>'`) → `make_plan` (`SeasonError` → 422 with its message).
- 200 body exactly as the design's JSON: top `plot_id, crop_id, planting_date, season_end, bucket_capacity_mm, threshold_mm, fetched_at, stale, days`; each day `date, et0_mm, rain_mm, kc, etc_mm, irrigation_mm, litres, run_minutes, bucket_end_mm, stale`. Rounding via `engine.round_half_up`: `kc` 3 dp, mm values 2 dp; `stale` per day = forecast `stale`.

- [ ] **Step 1: Failing tests** (fake registry + weather behind one MockTransport, router by host; demo plot with `planting_date` = forecast start − 99 days):

```python
def test_plan_shape_and_spec_numbers(api):   # 200; exact key sets; days[0] litres 6900, run_minutes 248, kc 1.15, bucket_end_mm 73.5; 7 days; stale False
def test_days_param(api):                    # days=3 → 3 rows; weather asked for days=3
@pytest.mark.parametrize("q", ["days=0", "days=8", "days=x", "days=2.5"])
def test_bad_days_is_422(api, q):            # VALIDATION, no upstream call made
def test_unknown_plot_is_404(api):
def test_registry_down_is_503(api):          # code UPSTREAM_UNAVAILABLE, detail startswith "registry-service unavailable"
def test_weather_down_is_503_with_retry_after(api):  # weather 503 + Retry-After 60 → ours 503, detail "weather-service unavailable…", Retry-After "60"
def test_registry_and_weather_down_names_registry(api):
def test_stale_forecast_marks_every_day(api):        # weather stale True → top and every day stale True; numbers computed
def test_truncated_plan_response(api):               # planting so today is day 144 → 2 rows, season_end tomorrow
def test_season_ended_is_422(api):                   # demo-like plot planted 2026-03-01 → 422 VALIDATION "Season ended on 2026-07-23 (day 145 of 145)…"
def test_unknown_crop_is_422(api):                   # crop_id "melon"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_plan_api.py -q` → Expected: FAIL (404 on the route).
- [ ] **Step 3: Implement** the lifespan, `get_http`, and the route in `main.py`.
- [ ] **Step 4: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 5: Live smoke (all three services, real Open-Meteo once).** Seed a throwaway registry DB in the scratchpad (`bash ../registry-service/seed_registry.sh <scratch>/registry.db`), run registry with `DATABASE_URL=sqlite:///<scratch>/registry.db` on 8000, weather on 8001, planner on 8002 (`cp .env.example .env` if absent). `curl` the demo North block plan → Expected: 422 "Season ended on 2026-07-23 …". `POST /v1/plots` a tomato plot (demo farm, loam, `dripnet-pc-1.0`, 1000 m², 1.5 × 0.4, lat 31.25 lon 34.79, planting today − 99 days) and get its plan → Expected: 200, 7 days from today, `run_minutes` > 0 on day 1, numbers consistent with `et0_mm × 1.15`. Stop weather-service and request the plan again → Expected: 503 `UPSTREAM_UNAVAILABLE`, detail starts `weather-service unavailable`. Stop registry → Expected: 503 `registry-service unavailable`. Stop everything; delete the scratch DB.
- [ ] **Step 6: Commit** `feat(planner): GET /v1/plots/{id}/plan`

### Task 5: README and CLAUDE.md

**Files:**
- Create: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: `README.md`** — run steps (port 8002, needs registry on 8000 and weather on 8001); config table (4 vars, the 20 s reason); the method in short (crop table, start at threshold, top-up rule, rain rule, drip conversion, truncation, season-ended 422, >1440 min note) with "full method and worked case: `.claude/skills/irrigation-calc-reference/SKILL.md`, AgroPilot planner method"; the design's JSON example (use the smoke-test output if available); error table; Mermaid `sequenceDiagram` (frontend → planner; planner → registry plot; alt 404 → 404; par soil/emitter/forecast; alt registry or weather fails → 503 UPSTREAM_UNAVAILABLE naming it; alt season over → 422; else 200 plan); test command.
- [ ] **Step 2: `CLAUDE.md`** — intro lists `planner-service` (port 8002); commands block; architecture bullets: `engine.py` pure and the only source of numbers, `crops.py` FAO table, `clients.py` validation + `UpstreamUnavailable`, call order and error precedence, skill section must stay in sync with the engine.
- [ ] **Step 3: Run** `uv run pytest -q` → Expected: all pass.
- [ ] **Step 4: Commit** `docs(planner): README and CLAUDE.md`
