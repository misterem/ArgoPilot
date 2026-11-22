# planner-service — design

Part 3 of P2 (the P2 task brief, `tasks/p2.md` in the course repo, not in this repo: "The `planner-service`" and "Global configurations"). New service in `services/planner-service`, port 8002. The FAO-56 research is `services/planner-service/docs/research/fao56.md`; the working reference is the `irrigation-calc-reference` skill (`.claude/skills/irrigation-calc-reference/SKILL.md`).

## Intent

Answer the grower's question: "Should I water this plot today, and for how many minutes?" For a plot, combine what registry-service knows (crop, planting date, soil, emitter, spacing, area, location) with weather-service's next days (ET0, rain) into a day-by-day drip plan: "Today: water for 248 minutes. Tomorrow: no need." Every number comes from a deterministic engine whose method is written down in the skill (FR-2.11); no AI model computes or adjusts numbers.

## Goals (spec)

- **FR-2.9** `GET /v1/plots/{id}/plan?days={days}`, `days` 1…7, default 7, starting today; the first day is today's recommendation.
- **FR-2.10** Each day has `date`, `et0_mm`, `kc`, `litres`, `run_minutes`, `stale`, and the bucket level at the end of the day; no irrigation → `run_minutes: 0`.
- **FR-2.11** Every number calculated as written in the skill, from the plot, its soil, its emitter, and the forecast for the plot's `lat`/`lon`.
- **FR-2.12** Bad `days` → `422 VALIDATION`; unknown plot → `404 NOT_FOUND`.
- **FR-2.13** A stale forecast still gives a plan; every affected day `stale: true`.
- **FR-2.14** registry-service or weather-service down or too slow → `503`, `code: UPSTREAM_UNAVAILABLE`, `detail` names the service. Never a plan of zeros.
- README with a JSON example; optional Mermaid sequence diagram (included). The brief says "Design the exact JSON yourself", so fields beyond FR-2.10 are allowed (the P1 "only spec'd fields" rule was for the registry API).
- The brief sets no latency target for the planner. "Doesn't answer in time" (FR-2.14) means an upstream call exceeds `REGISTRY_TIMEOUT_S` / `WEATHER_TIMEOUT_S`.
- Global configuration rules: pydantic-settings in one `config.py`, `.env.example` committed, clear startup error on a missing variable. `GET /health` for the frontend status line (FR-2.19).

## Non-goals

- No storage, no irrigation history, no soil sensors: each request computes the plan from scratch.
- No new registry fields or endpoints. No changes to `demo.sql` *(user)*: the demo plots are past their season and show the "season ended" error; a planting date can be PATCHed to see a plan.
- No climate adjustment of Kc (weather-service gives no wind or humidity), no dual Kc, no mulch, no staking, no drip-specific Kc ini, no root growth, no irrigation efficiency.

## Anti-goals

- A plan of zeros (or any "no irrigation" day) that the engine didn't actually decide.
- Numbers from anywhere but the engine (no AI, no defaults filling missing weather).
- Run times nobody can follow (the reason for the top-up rule below).

## Approaches considered

- **A. Async FastAPI; `clients.py` (httpx) for registry and weather; `crops.py` FAO table; `engine.py` pure functions.** *(Chosen by the user.)* The engine has no I/O and is tested against hand-worked cases; slow upstreams don't block other requests; soil, emitter and forecast are fetched in parallel.
- B. Sync FastAPI like the registry: familiar, but a weather call can take up to 20 s and holds a thread; calls run in sequence.
- C. Calculation inside the route: fewer files, but the agronomy is tangled with HTTP and harder to check by hand.

## The method (what the skill will say)

All decisions in this section are the user's unless marked *(agent)*. FAO references are FAO-56 equation/table numbers.

### Crop values (`crops.py`, single Kc, FAO Tables 11, 12, 22)

| | tomato | bell-pepper |
|---|---|---|
| Stage lengths ini/dev/mid/late (days) | 30 / 40 / 45 / 30 = 145 (Table 11 "Mediterranean, April/May") | 30 / 35 / 40 / 20 = 125 (Table 11 "Europe and Medit.", ini 30 matches the 125 total) |
| Kc ini / mid / end (Table 12, unadjusted) | 0.60 / 1.15 / 0.80 (end: middle of 0.70–0.90) | 0.60 / 1.05 / 0.90 |
| Root depth Zr, constant (Table 22, smaller end "for scheduling") | 0.7 m | 0.5 m |
| p, constant (Table 22) | 0.40 | 0.30 |

The registry's crop ids are the keys. A crop with no entry → `422 VALIDATION`, detail `No crop parameters for '<id>'`. *(agent)*

### Season

- Day number `i = (date − planting_date).days + 1` (planting day is day 1). Season length `L` = sum of the stages; the last season day is `planting_date + L − 1`.
- **Today past the season** (`i > L` on the plan's first date): `422 VALIDATION`, detail `Season ended on <last season day> (day <L> of <L>); update the planting date.` *(user: refuse, option A)*
- **Season ends inside the window:** the plan is **truncated** to the last season day; the response carries `season_end`. *(user)*
- `i < 1` (planting date after today; the registry forbids it, but the dates are compared across services) → `422`, detail `Season has not started (planting date <d>).` *(agent)*

### Kc on day i (Eq. 66)

Initial (`i ≤ Lini`): Kc ini. Development: `Kc ini + (i − Lini)/Ldev · (Kc mid − Kc ini)`. Mid: Kc mid. Late: `Kc mid + (i − Lini − Ldev − Lmid)/Llate · (Kc end − Kc mid)`.

### Bucket (Ch. 8)

- `TAW = available_water_mm_per_m (soil, from registry) × Zr` (Eq. 82, with available water = 1000 · (θFC − θWP)).
- `RAW = p × TAW` (Eq. 83). The **threshold**: irrigation keeps depletion `Dr ≤ RAW`.
- **Start of today:** `Dr = RAW` (bucket at the threshold this morning). *(user: option A)* Why: no sensor or history exists; assuming the grower last watered long enough ago leans toward not under-watering, and it gives a "today" answer.
- Bucket level reported = water left in the root zone = `TAW − Dr` (mm).

### Each day, in order *(agent, from FAO's order of a day, adapted to the top-up rule)*

1. `ETc = Kc × ET0` (Eq. 58).
2. **Effective rain:** `P = rain` if `rain ≥ 0.2 × ET0`, else 0 (Ch. 8, "can be ignored"). Runoff 0, capillary rise 0.
3. **Morning:** `Dr_start = max(0, Dr_prev − P)`; rain beyond the empty bucket drains (deep percolation).
4. **Decision:** if `Dr_start + ETc > RAW` (the level "would fall below" the threshold today), irrigate **net depth** `I = Dr_start + ETc − RAW`, so the day ends exactly at the threshold: `Dr_end = RAW`. Otherwise `I = 0` and `Dr_end = Dr_start + ETc`. *(user: "top up to the threshold", option A; FAO allows I ≤ Dr)* Exactly reaching RAW is not "below": no irrigation.
5. Clamp `0 ≤ Dr_end ≤ TAW` (Eq. 86).
6. Ks is not computed: depletion never exceeds RAW, so Ks = 1 (Eq. 84) every day.

### From depth to drip

- `litres = I × area_m2` (1 mm over 1 m² = 1 L).
- `emitters = area_m2 / (row_spacing_m × emitter_spacing_m)`; `flow_lph = emitters × emitter.flow_lph`.
- `run_minutes = litres / flow_lph × 60`, rounded half-up to a whole minute. No efficiency factor (the spec example has none).
- **More than a day of run time** (`run_minutes` > 1440): reported as computed, not capped or refused. *(agent)* It happens only when the drip system can't deliver the crop's daily use (e.g. rows 2 m, emitters 1 m at 0.6 L/h = 0.3 mm/h); capping would hide that and push the bucket below the threshold (Ks < 1, which the method doesn't model), refusing would hide the plan. The README says so.
- Spec check: 1000 m², Kc 1.15, ET0 6.0, no rain, rows 1.5 m, emitters 0.4 m at 1.0 L/h, starting at the threshold → I = 6.9 mm, `litres` 6900, `run_minutes` 248. ✔

### Worked case (test oracle)

Tomato, day 100 (mid-season, Kc 1.15), loam 175 mm/m → TAW 122.5, RAW 49.0; 1000 m², 1.5 m × 0.4 m, 1.0 L/h → 1666.67 L/h.

| Day | ET0 | Rain | P eff | Dr start | ETc | I (mm) | litres | run_minutes | Dr end | bucket_end_mm |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 6.0 | 0.0 | 0 | 49.00 | 6.90 | 6.90 | 6900 | 248 | 49.00 | 73.50 |
| 2 | 5.0 | 12.0 | 12.0 | 37.00 | 5.75 | 0 | 0 | 0 | 42.75 | 79.75 |
| 3 | 6.0 | 0.5 (< 1.2, ignored) | 0 | 42.75 | 6.90 | 0.65 | 650 | 23 | 49.00 | 73.50 |

(Day 3: 650 / 1666.67 × 60 = 23.4 → 23.)

### Skill update

FR-2.11 says numbers are calculated "as written in your skill". The `irrigation-calc-reference` skill gets a new section, "AgroPilot planner method", stating exactly this method (crop table, season rules, start at threshold, order of a day, top-up rule, drip conversion, rounding) and the worked case above, and the **open** markers it resolves point to it. The engine's tests use the skill's worked cases as oracles.

## API

`GET /v1/plots/{id}/plan?days=7`

```json
{
  "plot_id": "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002",
  "crop_id": "tomato",
  "planting_date": "2026-08-10",
  "season_end": "2027-01-01",
  "bucket_capacity_mm": 122.5,
  "threshold_mm": 73.5,
  "fetched_at": "2026-11-17T11:53:03Z",
  "stale": false,
  "days": [
    { "date": "2026-11-17", "et0_mm": 6.0, "rain_mm": 0.0, "kc": 1.15, "etc_mm": 6.9,
      "irrigation_mm": 6.9, "litres": 6900, "run_minutes": 248, "bucket_end_mm": 73.5, "stale": false }
  ]
}
```

*(agent: field set)* Top level: `season_end` (last season day), `bucket_capacity_mm` (TAW), `threshold_mm` (bucket level the plan keeps above: TAW − RAW), `fetched_at` and `stale` from weather-service (`stale` true if any day is). Per day: the spec's fields plus `rain_mm`, `etc_mm`, `irrigation_mm`, so the frontend and a reader can follow each number. Rounding *(agent)*: computed in full precision; output `kc` 3 decimals, mm values 2 decimals, `litres` whole litres (half-up), `run_minutes` whole minutes (half-up). `days` may be shorter than requested only when the season ends (see `season_end`).

Errors (problem+json, same shape as the other services; `problems.py` copied, with a way to set `code` explicitly):

| Status | `code` | When |
|---|---|---|
| 422 | `VALIDATION` | `days` not an integer 1…7; season ended or not started; crop without parameters |
| 404 | `NOT_FOUND` | registry says the plot doesn't exist; unknown route |
| 503 | `UPSTREAM_UNAVAILABLE` | registry or weather: connection error, timeout, non-2xx (other than the plot 404), non-JSON, missing/invalid field, or weather returning fewer/other days than asked. `detail`: `registry-service unavailable` or `weather-service unavailable` (plus a short reason) |

A weather-service `503` (provider down, nothing cached) is `503 UPSTREAM_UNAVAILABLE`, `weather-service unavailable`. `GET /health` → `{"status": "ok"}`, no upstream calls.

## Upstream calls *(agent)*

1. `GET {REGISTRY_URL}/v1/plots/{id}` (404 → our 404).
2. In parallel: `GET {REGISTRY_URL}/v1/soils/{soil_id}`, `GET {REGISTRY_URL}/v1/emitters/{emitter_id}`, `GET {WEATHER_URL}/v1/forecast?lat&lon&days={days}`.
- Weather's first date is "today" (local to the plot, as weather-service defines it); the planner never uses its own clock for dates.
- Weather answers are validated like weather-service validates Open-Meteo: exactly `days` consecutive days, every `et0_mm`/`rain_mm` a finite number ≥ 0; otherwise `503 weather-service unavailable`. Missing numbers are never defaulted (FR-2.8/FR-2.14).
- One `httpx.AsyncClient` per app (lifespan); per-service timeouts.

## Configuration (`.env`, all required)

| Variable | Example | Meaning |
|---|---|---|
| `REGISTRY_URL` | `http://127.0.0.1:8000` | registry-service base URL |
| `WEATHER_URL` | `http://127.0.0.1:8001` | weather-service base URL |
| `REGISTRY_TIMEOUT_S` | `5` | Timeout per registry call |
| `WEATHER_TIMEOUT_S` | `20` | Timeout per weather call; must exceed weather-service's worst case (~16 s with its example settings) |

## Code layout (flat modules)

- `main.py` (app, startup config check, route), `config.py`, `problems.py`
- `clients.py`: registry and weather calls, response validation, `Upstream(service)` errors and `PlotNotFound`
- `crops.py`: the FAO crop table
- `engine.py`: pure functions; inputs are plain dataclasses (plot, soil, emitter, crop, forecast days), output is plan rows; no I/O
- `tests/`: engine tests from the worked cases and the spec example; client tests with `httpx.MockTransport`; route tests with faked upstreams
- `README.md`: run, config, the method in short with a pointer to the skill, JSON example, error table, Mermaid sequence diagram (frontend → planner → registry → weather, with the 404 and 503 branches)

## Constraints

- Python 3.12 and 3.14; uv project, `package = false`.
- Services never import each other's code.
- No network in tests.

## Settled by the agent (builder check)

- **Which error wins:** a plot 404 first; then upstream 503s; season/crop 422s are checked after all upstream data is in (the season check needs weather's "today").
- **Days asked from weather:** always the requested `days`; truncation happens after.
- **Threshold comparison:** full precision, with a 1e-9 mm tolerance so float noise doesn't turn "exactly at the threshold" into an irrigation.
- **`Retry-After`:** a weather-service 503's `Retry-After` is forwarded on our 503; otherwise none.

## Left to the builder

- Dataclass names and field names inside the engine; how numbers are rounded internally (as long as output rounding is as above and comparisons use full precision).
- Log lines; test layout.
