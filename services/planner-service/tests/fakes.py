"""Fake registry-service and weather-service answers, served through httpx.MockTransport. No network."""

from datetime import date, timedelta

import httpx

TODAY = date(2026, 11, 17)
PLOT_ID = "c8f3d1b0-4d2e-5a1b-8b22-1d6e3f702002"
ET0 = [6.0, 5.0, 6.0, 5.5, 4.8, 5.2, 6.1]
RAIN = [0.0, 12.0, 0.5, 0.0, 0.0, 2.0, 0.0]


def plot_body(planting_date: date | str = TODAY - timedelta(days=99), **changes) -> dict:
    body = {
        "id": PLOT_ID,
        "farm_id": "b7e2c0a0-3c1d-4f0a-9a11-0c5d2e6f1001",
        "name": "North block",
        "area_m2": 1000.0,
        "crop_id": "tomato",
        "planting_date": planting_date if isinstance(planting_date, str) else planting_date.isoformat(),
        "soil_id": "loam",
        "row_spacing_m": 1.5,
        "emitter_spacing_m": 0.4,
        "emitter_id": "dripnet-pc-1.0",
        "lat": 31.25,
        "lon": 34.79,
    }
    body.update(changes)
    return body


SOIL = {"id": "loam", "name": "Loam", "available_water_mm_per_m": 175}
EMITTER = {"id": "dripnet-pc-1.0", "name": "DripNet PC", "flow_lph": 1.0}


def forecast_body(days: int = 7, start: date = TODAY, stale: bool = False) -> dict:
    return {
        "lat": 31.25,
        "lon": 34.79,
        "source": "open-meteo",
        "fetched_at": "2026-11-17T06:00:00Z",
        "stale": stale,
        "days": [
            {"date": (start + timedelta(days=i)).isoformat(), "et0_mm": ET0[i], "rain_mm": RAIN[i]} for i in range(days)
        ],
    }


class Upstreams:
    """Routes by host and path. Set `registry_down` / `weather_down`, or override a route's response."""

    def __init__(self):
        self.plot = plot_body()
        self.soil = SOIL
        self.emitter = EMITTER
        self.forecast_stale = False
        self.registry_down = False
        self.weather_down = False  # True → weather answers 503 with Retry-After: 60
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path  # decoded, as the real services see it (%2E → ".")
        if request.url.host == "registry.test":
            if self.registry_down:
                raise httpx.ConnectError("refused", request=request)
            if path == "/v1/plots":  # the registry's list route, as the real service answers it
                return httpx.Response(200, json=[self.plot])
            if path == f"/v1/plots/{PLOT_ID}":
                return httpx.Response(200, json=self.plot)
            if path.startswith("/v1/plots/"):
                return httpx.Response(404, json={"code": "NOT_FOUND"})
            if path == f"/v1/soils/{self.plot['soil_id']}":
                return httpx.Response(200, json=self.soil)
            if path == f"/v1/emitters/{self.plot['emitter_id']}":
                return httpx.Response(200, json=self.emitter)
        if request.url.host == "weather.test" and path == "/v1/forecast":
            if self.weather_down:
                return httpx.Response(503, headers={"Retry-After": "60"}, json={"code": "UNAVAILABLE"})
            days = int(request.url.params["days"])
            return httpx.Response(200, json=forecast_body(days, stale=self.forecast_stale))
        return httpx.Response(404)


def client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
