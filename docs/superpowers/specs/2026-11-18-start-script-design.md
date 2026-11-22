# One-command local start — short design

**Intent:** start the whole AgroPilot stack (registry 8000, weather 8001, planner 8002, frontend 3000) with one command or one click in PyCharm, including first-time setup, without touching the user's data or settings.

**Approaches:** *(agent's call, approved by the user)* a stdlib-only `start.py` at the repo root (chosen: no new tools, can do setup, one window, stops everything on Ctrl+C) vs docker-compose (needs images; spec wants local Postgres) vs a Procfile runner (honcho/overmind: extra install, no setup steps) vs a Makefile (poor at running and stopping four servers together).

**What it does, in order:**
1. Checks `uv`, `npm` are on PATH and ports 3000/8000/8001/8002 are free (clear message otherwise).
2. Copies each service's `.env.example` → `.env` (frontend: `.env.local`) **only if missing**.
3. `uv sync` in each Python service; `npm install` only when `node_modules` is missing or older than `package-lock.json`.
4. Registry database, read through the registry's own `config.py` (so env-beats-.env holds): SQLite file missing → `seed_registry.sh` (needs `sqlite3`); PostgreSQL not answering → stop with the `brew services start postgresql@16` hint; PostgreSQL without tables → warning with the `scripts/setup_db.py` hint (never runs it). Never prints the password.
5. Starts registry → weather → planner → frontend, each in its own process group, output prefixed and coloured per service; waits for each to answer (`/health`, frontend `/`) before starting the next.
6. Prints the URLs and opens http://localhost:3000.
7. Ctrl+C stops all four; if one exits, stops the others and names it.

**Run:** `uv run start.py` (PEP 723 header pins Python ≥ 3.12 via uv; the code also runs on the machine's Python 3.8). PyCharm: shared run configuration `.run/Start AgroPilot.run.xml` (Shell Script, runs `uv run start.py` in the terminal so PATH and Ctrl+C work).

**Non-goals:** no demo-data changes, no production mode, no Docker.

**Verification:** run it end to end (fresh and existing env files untouched; services healthy; browser opens; Ctrl+C stops all; a busy port is reported).
