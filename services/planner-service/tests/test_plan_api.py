from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from conftest import assert_problem
from fakes import PLOT_ID, TODAY, Upstreams, client_for, plot_body
from main import app, get_http

URL = f"/v1/plots/{PLOT_ID}/plan"
DAY_KEYS = {"date", "et0_mm", "rain_mm", "kc", "etc_mm", "irrigation_mm", "litres", "run_minutes", "bucket_end_mm", "stale"}
TOP_KEYS = {"plot_id", "crop_id", "planting_date", "season_end", "bucket_capacity_mm", "threshold_mm", "fetched_at", "stale", "days"}


@pytest.fixture
def api():
    up = Upstreams()
    http = client_for(up)
    app.dependency_overrides[get_http] = lambda: http
    with TestClient(app) as client:
        yield client, up
    app.dependency_overrides.clear()


def test_plan_shape_and_spec_numbers(api):
    client, _ = api
    r = client.get(URL)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == TOP_KEYS
    assert (body["plot_id"], body["crop_id"], body["planting_date"]) == (PLOT_ID, "tomato", "2026-08-10")
    assert (body["season_end"], body["bucket_capacity_mm"], body["threshold_mm"]) == ("2027-01-01", 122.5, 73.5)
    assert (body["fetched_at"], body["stale"]) == ("2026-11-17T06:00:00Z", False)
    assert len(body["days"]) == 7
    assert all(set(d) == DAY_KEYS for d in body["days"])
    assert body["days"][0] == {"date": "2026-11-17", "et0_mm": 6.0, "rain_mm": 0.0, "kc": 1.15, "etc_mm": 6.9,
                               "irrigation_mm": 6.9, "litres": 6900, "run_minutes": 248, "bucket_end_mm": 73.5,
                               "stale": False}
    assert [(d["litres"], d["run_minutes"]) for d in body["days"][:3]] == [(6900, 248), (0, 0), (650, 23)]


def test_days_param(api):
    client, up = api
    assert len(client.get(URL, params={"days": 3}).json()["days"]) == 3
    weather = [r for r in up.requests if r.url.host == "weather.test"][0]
    assert weather.url.params["days"] == "3"


@pytest.mark.parametrize("q", ["days=0", "days=8", "days=x", "days=2.5", "days=-1"])
def test_bad_days_is_422(api, q):
    client, up = api
    assert_problem(client.get(f"{URL}?{q}"), 422, "VALIDATION")
    assert up.requests == []


def test_unknown_plot_is_404(api):
    client, up = api
    body = assert_problem(client.get("/v1/plots/nope/plan"), 404, "NOT_FOUND")
    assert body["detail"] == "Plot not found"
    assert all(r.url.host == "registry.test" for r in up.requests)


def test_registry_down_is_503(api):
    client, up = api
    up.registry_down = True
    body = assert_problem(client.get(URL), 503, "UPSTREAM_UNAVAILABLE")
    assert body["detail"].startswith("registry-service unavailable")


def test_weather_down_is_503_with_retry_after(api):
    client, up = api
    up.weather_down = True
    r = client.get(URL)
    body = assert_problem(r, 503, "UPSTREAM_UNAVAILABLE")
    assert body["detail"].startswith("weather-service unavailable")
    assert r.headers["retry-after"] == "60"


def test_registry_and_weather_down_names_registry(api):
    client, up = api
    up.weather_down = True
    up.soil = {"id": "loam"}  # registry answers the plot, then a broken soil
    body = assert_problem(client.get(URL), 503, "UPSTREAM_UNAVAILABLE")
    assert body["detail"].startswith("registry-service unavailable")


def test_stale_forecast_marks_every_day(api):
    client, up = api
    up.forecast_stale = True
    body = client.get(URL).json()
    assert body["stale"] is True
    assert all(d["stale"] is True for d in body["days"])
    assert body["days"][0]["run_minutes"] == 248


def test_truncated_plan_response(api):
    client, up = api
    up.plot = plot_body(planting_date=TODAY - timedelta(days=143))
    body = client.get(URL).json()
    assert len(body["days"]) == 2
    assert body["season_end"] == "2026-11-18"
    assert body["days"][-1]["date"] == "2026-11-18"


def test_season_ended_is_422(api):
    client, up = api
    up.plot = plot_body(planting_date=date(2026, 3, 1))
    body = assert_problem(client.get(URL), 422, "VALIDATION")
    assert body["detail"] == "Season ended on 2026-07-23 (day 145 of 145); update the planting date."


def test_unknown_crop_is_422(api):
    client, up = api
    up.plot = plot_body(crop_id="melon")
    body = assert_problem(client.get(URL), 422, "VALIDATION")
    assert body["detail"] == "No crop parameters for 'melon'"


@pytest.mark.parametrize("path", ["/v1/plots/%2E/plan", "/v1/plots/%2E%2E/plan"])
def test_dot_plot_id_is_404_not_outage(api, path):
    client, _ = api
    assert_problem(client.get(path), 404, "NOT_FOUND")
