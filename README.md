# AgroPilot

AgroPilot helps a grower manage agricultural crops with modern AI. 


## Run everything

One command sets up and starts all four services (registry 8000, weather 8001, planner 8002, frontend 3000) and opens http://localhost:3000:

```bash
uv run start.py
```

In PyCharm, pick **Start AgroPilot** in the run configurations and press Run.

It needs `uv` and Node.js (`npm`). The first time, it creates each service's `.env` from its `.env.example` (only when missing), installs dependencies, and creates the SQLite registry database from the seed if your `.env` points at SQLite. If `DATABASE_URL` points at PostgreSQL, PostgreSQL must be running (`brew services start postgresql@16`). Ctrl+C stops everything.

The demo plots' growing seasons are over, so their pages say "No plan: the season ended". To see a full plan, move a plot's planting date into the season, for example:

```bash
curl -X PATCH http://127.0.0.1:8000/v1/plots/c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002 -H 'content-type: application/json' -d '{"planting_date":"2026-08-11"}'
```

## Services

Each service lives in its own folder under `services/`, with its own README:

| Service | Port | What it does |
|---|---|---|
| `registry-service` | 8000 | Farms, plots, and the crop, soil and emitter catalogues (SQLite or PostgreSQL) |
| `weather-service` | 8001 | Daily ET0 and rain from Open-Meteo, cached per 0.1° cell |
| `planner-service` | 8002 | The day-by-day drip irrigation plan for a plot (FAO-56) |
| `frontend` | 3000 | The web app growers use |

Every service answers `GET /health` with `{"status": "ok"}`.
