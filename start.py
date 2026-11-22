# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Start the whole AgroPilot stack for local development, with first-time setup.

    uv run start.py

1. Checks the tools (uv, npm) and that ports 8000, 8001, 8002 and 3000 are free.
2. Creates each service's .env (frontend: .env.local) from its .env.example, only if missing.
3. Installs dependencies (uv sync; npm install when node_modules is missing or out of date).
4. Checks the registry database: creates the SQLite file from the seed if missing; for PostgreSQL,
   checks that it answers (it never creates tables or loads data there).
5. Starts registry, weather, planner and frontend in that order, waiting for each to answer,
   then opens http://localhost:3000.
6. Ctrl+C stops everything. If one service stops on its own, the others are stopped too.

Standard library only. Runs on Python 3.8+ too (`python3 start.py`).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICES = ROOT / "services"
FRONTEND_URL = "http://localhost:3000"

COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


class Service:
    def __init__(self, name: str, folder: str, port: int, command: list, ready_path: str, color: str, wait_s: int):
        self.name = name
        self.dir = SERVICES / folder
        self.port = port
        self.command = command
        self.ready_url = f"http://127.0.0.1:{port}{ready_path}"
        self.color = color
        self.wait_s = wait_s
        self.process: subprocess.Popen | None = None

    @property
    def tag(self) -> str:
        return paint(f"[{self.name:<8}]", self.color)


def uvicorn(port: int) -> list:
    return ["uv", "run", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)]


STACK = [
    Service("registry", "registry-service", 8000, uvicorn(8000), "/health", "36", 30),
    Service("weather", "weather-service", 8001, uvicorn(8001), "/health", "33", 30),
    Service("planner", "planner-service", 8002, uvicorn(8002), "/health", "35", 30),
    # The first request compiles the app, so the frontend gets longer.
    Service("frontend", "frontend", 3000, ["npm", "run", "dev", "--", "--port", "3000"], "/", "32", 120),
]


def say(text: str) -> None:
    print(paint("[start   ]", "1") + " " + text, flush=True)


def fail(text: str) -> None:
    print(paint("[start   ]", "1") + " " + paint(text, "31"), file=sys.stderr, flush=True)
    sys.exit(1)


def child_env() -> dict:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)  # each service uses its own .venv through uv
    if COLOR:
        env.setdefault("FORCE_COLOR", "1")
    return env


def run(command: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=child_env(), capture_output=True, text=True)


# --- 1. tools and ports ---

def check_tools() -> None:
    missing = [tool for tool in ("uv", "npm") if shutil.which(tool) is None]
    if missing:
        fail(f"Not found on PATH: {', '.join(missing)}. Install them (uv: https://docs.astral.sh/uv/, npm: Node.js) and try again.")


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_ports() -> None:
    busy = [f"{s.port} ({s.name})" for s in STACK if port_in_use(s.port)]
    if busy:
        fail(f"Port in use: {', '.join(busy)}. Stop whatever is running there (maybe an earlier start) and try again.")


# --- 2. env files ---

def ensure_env_files() -> None:
    for service in STACK:
        example = service.dir / ".env.example"
        target = service.dir / (".env.local" if service.name == "frontend" else ".env")
        if not target.exists():
            shutil.copyfile(example, target)
            say(f"Created {target.relative_to(ROOT)} from .env.example")


# --- 3. dependencies ---

def install() -> None:
    for service in STACK[:3]:
        say(f"{service.name}: uv sync")
        result = run(["uv", "sync", "--quiet"], service.dir)
        if result.returncode != 0:
            fail(f"uv sync failed in {service.dir.relative_to(ROOT)}:\n{result.stderr.strip()}")
    frontend = STACK[3]
    stamp = frontend.dir / "node_modules" / ".package-lock.json"
    lock = frontend.dir / "package-lock.json"
    if not stamp.exists() or stamp.stat().st_mtime < lock.stat().st_mtime:
        say("frontend: npm install")
        result = run(["npm", "install", "--no-audit", "--no-fund"], frontend.dir)
        if result.returncode != 0:
            fail(f"npm install failed:\n{result.stderr.strip()}")


# --- 4. registry database ---

# Runs inside registry-service, so DATABASE_URL is read exactly as the service reads it.
_DB_PROBE = """
import json, sys
import config, db, schema
from sqlalchemy import make_url
try:
    url = config.get_settings().database_url
except config.ConfigError as exc:
    print(json.dumps({"kind": "error", "message": str(exc)})); sys.exit(0)
u = make_url(url)
if u.get_backend_name() == "sqlite":
    path = (db.SERVICE_DIR / (u.database or "registry.db")).resolve()
    print(json.dumps({"kind": "sqlite", "path": str(path), "exists": path.exists()}))
else:
    info = {"kind": "postgres", "where": f"{u.host or 'localhost'}:{u.port or 5432}/{u.database}"}
    try:
        with db.get_engine(url).connect() as conn:
            info["tables"] = len(schema.existing_tables(conn))
        info["ok"] = True
    except Exception as exc:
        info["ok"] = False
        info["error"] = type(exc).__name__
    print(json.dumps(info))
"""


def check_database() -> None:
    registry = STACK[0]
    result = run(["uv", "run", "python", "-c", _DB_PROBE], registry.dir)
    try:
        info = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        fail(f"Couldn't read the registry's database settings:\n{result.stderr.strip()}")
    if info["kind"] == "error":
        fail(f"registry: {info['message']}")
    if info["kind"] == "sqlite":
        if info["exists"]:
            say(f"registry: SQLite database {info['path']}")
            return
        if shutil.which("sqlite3") is None:
            fail(f"registry: {info['path']} doesn't exist, and creating it needs the sqlite3 command-line tool.")
        say(f"registry: creating {info['path']} from the seed")
        seeded = run(["bash", "seed_registry.sh", info["path"]], registry.dir)
        if seeded.returncode != 0:
            fail(f"seed_registry.sh failed:\n{seeded.stderr.strip()}")
        return
    if not info["ok"]:
        fail(
            f"registry: PostgreSQL at {info['where']} isn't answering ({info['error']}). "
            "Start it (e.g. `brew services start postgresql@16`) or point DATABASE_URL in "
            "services/registry-service/.env at SQLite."
        )
    say(f"registry: PostgreSQL at {info['where']}")
    if info["tables"] == 0:
        say(paint(
            "registry: that database has no tables yet, so the registry will answer 503. Set it up once with: "
            "cd services/registry-service && uv run python scripts/setup_db.py", "33"))


# --- 5. processes ---

def pipe_output(service: Service) -> None:
    assert service.process is not None and service.process.stdout is not None
    for line in service.process.stdout:
        print(f"{service.tag} {line.rstrip()}", flush=True)


def start(service: Service) -> None:
    service.process = subprocess.Popen(
        service.command,
        cwd=service.dir,
        env=child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,  # its own process group, so stopping it also stops uvicorn/next children
    )
    threading.Thread(target=pipe_output, args=(service,), daemon=True).start()


def answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status < 500
    except Exception:
        return False


def wait_ready(service: Service) -> None:
    deadline = time.monotonic() + service.wait_s
    while time.monotonic() < deadline:
        if service.process is not None and service.process.poll() is not None:
            fail(f"{service.name} stopped while starting (exit code {service.process.returncode}); see its output above.")
        if answers(service.ready_url):
            say(f"{service.name} is up on port {service.port}")
            return
        time.sleep(0.5)
    fail(f"{service.name} didn't answer {service.ready_url} within {service.wait_s} s; see its output above.")


def stop_all() -> None:
    running = [s for s in STACK if s.process is not None and s.process.poll() is None]
    for service in running:
        try:
            os.killpg(service.process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + 8
    for service in running:
        try:
            service.process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(service.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def main() -> None:
    if os.name != "posix":
        fail("start.py runs on macOS and Linux (on Windows, use WSL).")
    check_tools()
    check_ports()
    ensure_env_files()
    install()
    check_database()
    try:
        for service in STACK:
            say(f"starting {service.name}…")
            start(service)
            wait_ready(service)
        say(paint(f"All four services are up. Open {FRONTEND_URL}  (Ctrl+C stops everything)", "1;32"))
        webbrowser.open(FRONTEND_URL)
        while True:
            for service in STACK:
                if service.process is not None and service.process.poll() is not None:
                    raise RuntimeError(f"{service.name} stopped (exit code {service.process.returncode}); stopping the others.")
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        say("stopping…")
        stop_all()
        say("stopped.")
    except RuntimeError as exc:
        print(paint(f"[start   ] {exc}", "31"), file=sys.stderr, flush=True)
        stop_all()
        sys.exit(1)
    except SystemExit:
        stop_all()
        raise


if __name__ == "__main__":
    main()
