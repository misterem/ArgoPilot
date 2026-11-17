# weather-service — design

Part 2 of P2 (the P2 task brief, `tasks/p2.md` in the course repo, not in this repo: "The `weather-service`" and "Global configurations"; the goals below are its complete list for this service). New service in `services/weather-service`, port 8001.

Callers are other services only: the frontend fetches on its server, and "the browser never calls the services", so no CORS.

## Intent

The planner needs, for a plot's location, how much water the field will lose each day (ET0) and how much rain will put back, for today and the next 6 days. `weather-service` gets that from Open-Meteo ("the provider") and serves it to the rest of AgroPilot. Its job is to stay useful when the provider is slow or down, without ever inventing numbers: a forecast of zeros reads as "no water needed", the worst bug this system can have (FR-2.8).

## Goals (spec)

- **FR-2.3** `GET /v1/forecast?lat={lat}&lon={lon}&days={days}` returns, for each of the next `days` days starting today: `date`, `et0_mm`, `rain_mm`.
- **FR-2.4** `lat` −90…90, `lon` −180…180, `days` 1…7; otherwise `422`, `code: VALIDATION`.
- **FR-2.5** Requests in the same 0.1° grid cell share one forecast; a forecast is fresh for 3 hours, and while fresh the provider is not called.
- **FR-2.6** Provider failure (timeout, error status, non-JSON body, missing field) → retry twice, then answer with the last forecast for that cell and `stale: true`.
- **FR-2.7** Provider failure and no usable earlier forecast → `503`, `code: UNAVAILABLE`, `Retry-After` header.
- **FR-2.8** Never a number the provider didn't give. No zeros, no defaults, no filled-in days.
- **NFR-2.3** Fresh forecast (no provider call): p95 ≤ 100 ms at 10 rps.
- Settings via pydantic-settings in one `config.py`; `.env.example` committed with every variable; clear startup error when a required variable is missing.
- `GET /health` (the frontend's status line, FR-2.19, calls it).

Response example (from the spec):

```json
{
  "lat": 31.25, "lon": 34.79, "source": "open-meteo",
  "fetched_at": "2026-11-12T06:00:00Z", "stale": false,
  "days": [{ "date": "2026-11-12", "et0_mm": 3.1, "rain_mm": 0.0 }, "..."]
}
```

## Non-goals

- Knows nothing about farms, plots or crops; coordinates and dates only.
- No database or persistent cache: the cache lives in process memory and a restart empties it.
- No endpoints beyond `/v1/forecast` and `/health`.
- No other providers now; switching provider or plan is a config change (base URL, API key) plus a new `provider.py`, nothing else.

## Anti-goals

- A `200` whose numbers didn't come from the provider (zero-filled day, default value, a day shifted from another date).
- Cached answers slowed down by a provider outage (the outage is exactly when the cache matters).
- Open-Meteo field names anywhere outside the code that calls it.

## Approaches considered

- **A. Async FastAPI, `httpx.AsyncClient`, own in-memory cache with one `asyncio.Lock` per grid cell.** *(Chosen by the user.)* Cached answers never wait on a provider call; concurrent requests for one cell share one provider call; we own the fresh/stale/too-old rules.
- B. Sync FastAPI with `httpx.Client` in the thread pool. Familiar (the registry is sync), but during an outage each waiting request holds a pool thread for up to ~15 s, and a burst can stall cached answers too.
- C. A cache library (`cachetools` TTLCache, `aiocache`). TTL eviction deletes exactly the expired entries the stale fallback needs.

## Decisions

### Provider (Open-Meteo)

*(All in this section: agent's proposal, accepted by the user.)*

- Endpoint `{PROVIDER_BASE_URL}/v1/forecast`, free base URL `https://api.open-meteo.com`.
- Daily variables: **`et0_fao_evapotranspiration`** (mm/day, FAO-56 Penman-Monteith reference ET for grass) → `et0_mm`; **`precipitation_sum`** (mm/day; rain + showers + snowfall as water) → `rain_mm`. Not `rain_sum`, which excludes showers and would undercount water the field received. Both names and units go in the README.
- `timezone=auto`: dates are the local calendar dates at the point, so "today" is the grower's today. The response's `utc_offset_seconds` is kept with the cached forecast to know the local date later.
- `forecast_days=8` (one more than the API maximum of 7, see "Too old").
- `apikey` sent only when `PROVIDER_API_KEY` is non-empty (paid plans use a `customer-` host, set via `PROVIDER_BASE_URL`).
- Open-Meteo errors are `400 {"error": true, "reason": ...}`; treated like any other error status.

### Grid cell

- A cell is a 0.1° square cut at 0.1° steps: `cell_lat = floor(lat × 10) / 10`, same for lon (computed so float error can't push 31.3 into the 31.2 cell). 31.25 and 31.29 share cell 31.2; 31.30 is in 31.3.
- Edges: `lat = 90` belongs to cell 89.9, `lon = 180` to cell 179.9, so every cell centre is a valid coordinate.
- The provider is always asked for the **cell centre** (cell + 0.05), so the forecast doesn't depend on which request came first. The response echoes the `lat`/`lon` the caller sent.

### Cache, freshness, stale, too old

- One entry per cell: the validated days, `fetched_at` (UTC), `utc_offset_seconds`.
- **Fresh:** `now − fetched_at < FORECAST_FRESH_HOURS` (3 h). Served without calling the provider.
- **Covers the request:** the entry has every date from local today (now + offset) through today + `days` − 1. An entry that doesn't cover the request is treated as not fresh (fetch again).
- **Not fresh:** call the provider: 1 attempt + `PROVIDER_RETRIES` (2) retries, waiting `PROVIDER_RETRY_BACKOFF_S` between attempts. Success replaces the entry, `stale: false`.
- **All attempts failed:** if the cell has an entry younger than `FORECAST_MAX_STALE_HOURS` that covers the request, answer from it with `stale: true` and its original `fetched_at`. Otherwise `503 UNAVAILABLE` with `Retry-After: RETRY_AFTER_S`.
- **Too old = 24 hours.** *(User.)* Why (goes in the README): ET0 forecasts are refreshed several times a day; a forecast older than a day has missed every update since, and serving it as if it described today's sun and wind risks a wrong irrigation decision, so past that point an honest `503` is better than an old guess. Fetching 8 days means a forecast up to 24 h old has crossed at most one local midnight and still covers today + 6 days, so a stale answer always has all 7 days the planner asks for.
- **Concurrency (single flight per cell):** at most one fetch cycle (attempt + retries) runs per cell at a time. A request that finds no fresh, covering entry and no fetch in flight starts one; a request that arrives while one is in flight for its cell waits for it and gets **its outcome**: the new forecast on success, or the same stale answer / `503` on failure. It does not start a cycle of its own afterwards. Worst-case wait is one cycle (~16 s), however many requests queue. A fresh-cache hit never waits. *(Agent's call, from FR-2.5 "share one forecast".)*
- **No failure memory.** *(User: "closest to FR-2.6".)* Once a cycle has finished, the next request that finds no fresh entry calls the provider again with full retries, even if the previous cycle failed a moment ago. Considered and rejected: pausing provider calls for `RETRY_AFTER_S` after a failure (answers faster in long outages, but skips the provider call FR-2.6 describes).
- The entry is replaced only by a successful, fully validated fetch; a failed fetch never removes or edits it.

### What counts as a provider failure

Any of these, on any attempt: timeout or connection error; non-2xx status; body not JSON; `daily` or one of `time` / `et0_fao_evapotranspiration` / `precipitation_sum` missing; arrays of different lengths; any `null` value; a value that isn't a number; a date that doesn't parse; fewer days than needed to cover today + 6; `utc_offset_seconds` missing. *(Agent's proposal, accepted.)* A response with one bad day is rejected whole; days are never patched.

### API

- `days` is required (the planner always sends it); missing → `422`.
- Response fields exactly as the spec example; `fetched_at` is UTC ISO 8601 with `Z`, second precision; `source` is `"open-meteo"`; numbers are passed through as the provider gave them (no rounding).
- Errors: RFC 9457 `application/problem+json` with `code`, same shape as registry-service (`problems.py` copied, not imported): `422 VALIDATION`, `404 NOT_FOUND` (unknown route), `503 UNAVAILABLE` with `Retry-After`. The 503 `detail` says the provider is unavailable and no recent forecast exists for that location.
- `GET /health` → `200 {"status": "ok"}`; it does not call the provider.

### Configuration (`.env`, all required)

| Variable | Example | Meaning |
|---|---|---|
| `PROVIDER_BASE_URL` | `https://api.open-meteo.com` | Provider base URL |
| `PROVIDER_API_KEY` | *(empty)* | Must be present; may be empty (free tier) |
| `PROVIDER_TIMEOUT_S` | `5` | Per-attempt timeout |
| `PROVIDER_RETRIES` | `2` | Retries after the first attempt |
| `PROVIDER_RETRY_BACKOFF_S` | `0.5` | Wait between attempts |
| `FORECAST_FRESH_HOURS` | `3` | Freshness window |
| `FORECAST_MAX_STALE_HOURS` | `24` | Oldest forecast served as stale |
| `RETRY_AFTER_S` | `60` | `Retry-After` on 503 |

Worst-case response time when the provider is down: 3 × 5 s + 2 × 0.5 s = 16 s. The planner's timeout for weather-service must be longer than that (noted for Part 3).

### Code layout (flat modules, like registry-service)

- `main.py` (app, startup config check, routes), `config.py`, `problems.py`
- `provider.py`: the only place that knows Open-Meteo's URL parameters and field names; returns validated days or raises a provider error
- `forecast.py`: grid cell, cache, freshness/stale rules, retries, per-cell locks
- `tests/` with a fake provider via `httpx.MockTransport` and an injectable clock; no network in tests
- `scripts/measure_latency.py` for NFR-2.3
- `README.md`: run, config, Open-Meteo variables and units, too-old rule and why, response example, Mermaid sequence diagram (request → fresh? → provider call → retry → stale answer / 503)

## Constraints

- Python 3.12 and 3.14; uv project, `package = false`, like registry-service.
- Services never import each other's code.
- `.env` never committed; `.env.example` committed.

## Left to the builder

- Exact backoff shape (fixed wait is fine), log lines, test layout.
- How the clock is injected, and how the provider client is created and closed (lifespan).
- Wording of 422/503 `detail` text.
