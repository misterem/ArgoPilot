import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app

SERVICE_DIR = Path(__file__).resolve().parents[1]

DEMO_FARM = "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001"
EAST_FARM = "a9c1e4b2-6f70-4d8e-a144-3f8b5c904004"
NORTH_BLOCK = "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client backed by a freshly seeded database in a temp folder."""
    db = tmp_path / "registry.db"
    subprocess.run(["bash", str(SERVICE_DIR / "seed_registry.sh"), str(db)], check=True, capture_output=True)
    monkeypatch.setenv("REGISTRY_DB", str(db))
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
