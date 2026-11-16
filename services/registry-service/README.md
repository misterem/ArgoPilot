# registry-service

The AgroPilot registry: farms, plots, and read-only catalogues of crops, soils, and drip emitters. It runs on FastAPI with a single SQLite file, `registry.db`.

## Run

```bash
uv sync
bash seed_registry.sh            # creates a fresh registry.db (deletes the old one)
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs. To use another database file, set `REGISTRY_DB=/path/to/file.db`.

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
| 503 | `UNAVAILABLE` | Database file missing or unreadable (sends `Retry-After`) |

## Code layout

- `main.py`: builds the app and wires in the routers
- `farms.py`, `plots.py`, `catalogue.py`: the routes
- `models.py`: request and response models and their validation rules
- `problems.py`: the problem+json error responses
- `db.py`: the SQLite connection, one per request

## Test

```bash
uv run pytest
```

Each test runs against a freshly seeded copy of the database in a temp folder, so `registry.db` is never touched.

## Latency (NFR-1.1)

With the server running:

```bash
uv run python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --seconds 60
```

It sends 10 req/s round-robin across every list and get-by-id route and prints p50/p95/max.
