import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# main.py refuses to import without DATABASE_URL. Overwrite (not setdefault) any shell value with a file
# that never exists, so a test that forgets to set its own URL gets 503, never a real database.
os.environ["DATABASE_URL"] = "sqlite:///__tests_must_set_DATABASE_URL__.db"

import config  # noqa: E402
import db  # noqa: E402
from main import app  # noqa: E402
from schema import load  # noqa: E402

SERVICE_DIR = Path(__file__).resolve().parents[1]

DEMO_FARM = "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
EAST_FARM = "a9c1e4b2-6f70-4d8e-a144-3f8b5c904004"
NORTH_BLOCK = "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"


TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
BACKENDS = ["sqlite"] + (["postgres"] if TEST_POSTGRES_URL else [])
requires_postgres = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="set TEST_POSTGRES_URL")


@pytest.fixture(autouse=True)
def _fresh_settings():
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture(params=BACKENDS)
def client(request, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client backed by a freshly seeded database (SQLite in a temp folder, or Postgres)."""
    if request.param == "postgres":
        with db.get_engine(db.engine_url(TEST_POSTGRES_URL)).begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA public CASCADE")
            conn.exec_driver_sql("CREATE SCHEMA public")
            load(conn, "schema.sql", "catalogue.sql", "demo.sql")
        monkeypatch.setenv("DATABASE_URL", TEST_POSTGRES_URL)
    else:
        path = tmp_path / "registry.db"
        subprocess.run(["bash", str(SERVICE_DIR / "seed_registry.sh"), str(path)], check=True, capture_output=True)
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    return TestClient(app)


@pytest.fixture
def plot_body() -> dict:
    return {
        "farm_id": DEMO_FARM,
        "name": "South block",
        "area_m2": 1000,
        "crop_id": "tomato",
        "planting_date": "2026-03-01",
        "soil_id": "loam",
        "row_spacing_m": 1.5,
        "emitter_spacing_m": 0.4,
        "emitter_id": "dripnet-pc-1.0",
        "lat": 31.25,
        "lon": 34.79,
    }


def assert_problem(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["status"] == status
    assert body["code"] == code
    assert body["title"] and body["detail"]
    return body
