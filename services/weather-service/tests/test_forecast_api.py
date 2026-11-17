from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

import config
import provider
from conftest import assert_problem
from fakes import good_body
from forecast import Forecaster
from main import app, get_forecaster

T0 = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)


class Upstream:
    """Fake Open-Meteo: serves good_body() while up, 503 while down."""

    def __init__(self):
        self.up = True
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        return httpx.Response(200, json=good_body()) if self.up else httpx.Response(503)


class Clock:
    def __init__(self):
        self.at = T0

    def __call__(self):
        return self.at


async def _no_sleep(_):
    return None


@pytest.fixture
def world():
    upstream, clock = Upstream(), Clock()
    http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    settings = config.load_settings(None)
    forecaster = Forecaster(
        fetch=lambda la, lo: provider.fetch_daily(http, settings, la, lo), settings=settings, now=clock, sleep=_no_sleep
    )
    app.dependency_overrides[get_forecaster] = lambda: forecaster
    with TestClient(app) as client:
        yield client, upstream, clock
    app.dependency_overrides.clear()


def test_forecast_shape(world):
    client, _, _ = world
    r = client.get("/v1/forecast", params={"lat": 31.25, "lon": 34.79, "days": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"lat", "lon", "source", "fetched_at", "stale", "days"}
    assert (body["lat"], body["lon"], body["source"], body["stale"]) == (31.25, 34.79, "open-meteo", False)
    assert body["fetched_at"] == "2026-11-17T06:00:00Z"
    assert len(body["days"]) == 7
    assert body["days"][0] == {"date": "2026-11-17", "et0_mm": 3.1, "rain_mm": 0.0}
    assert body["days"][1] == {"date": "2026-11-18", "et0_mm": 2.8, "rain_mm": 4.2}


def test_days_param(world):
    client, _, _ = world
    assert len(client.get("/v1/forecast?lat=31.25&lon=34.79&days=1").json()["days"]) == 1


@pytest.mark.parametrize("query", [
    "lat=91&lon=0&days=7", "lat=-91&lon=0&days=7", "lat=0&lon=181&days=7", "lat=0&lon=-181&days=7",
    "lat=0&lon=0&days=0", "lat=0&lon=0&days=8", "lat=0&lon=0", "lon=0&days=7", "lat=0&days=7",
    "lat=abc&lon=0&days=7", "lat=nan&lon=0&days=7", "lat=0&lon=inf&days=7", "lat=0&lon=0&days=2.5",
])
def test_bad_query_is_422(world, query):
    client, upstream, _ = world
    assert_problem(client.get(f"/v1/forecast?{query}"), 422, "VALIDATION")
    assert upstream.calls == 0


@pytest.mark.parametrize("query", ["lat=90&lon=180&days=7", "lat=-90&lon=-180&days=1"])
def test_bounds_are_inclusive(world, query):
    client, _, _ = world
    assert client.get(f"/v1/forecast?{query}").status_code == 200


def test_provider_down_no_cache_is_503(world):
    client, upstream, _ = world
    upstream.up = False
    body = assert_problem(client.get("/v1/forecast?lat=31.25&lon=34.79&days=7"), 503, "UNAVAILABLE")
    assert "provider" in body["detail"].lower()
    assert upstream.calls == 3


def test_503_has_retry_after(world):
    client, upstream, _ = world
    upstream.up = False
    assert client.get("/v1/forecast?lat=31.25&lon=34.79&days=7").headers["retry-after"] == "60"


def test_provider_down_with_cache_is_stale(world):
    client, upstream, clock = world
    fresh = client.get("/v1/forecast?lat=31.25&lon=34.79&days=7").json()
    clock.at += timedelta(hours=4)
    upstream.up = False
    stale = client.get("/v1/forecast?lat=31.25&lon=34.79&days=7").json()
    assert stale["stale"] is True
    assert stale["fetched_at"] == fresh["fetched_at"]
    assert stale["days"] == fresh["days"]
