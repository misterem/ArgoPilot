import copy
from datetime import date

import httpx
import pytest

import clients
import config
from engine import WeatherDay
from fakes import EMITTER, PLOT_ID, SOIL, TODAY, Upstreams, client_for, forecast_body, plot_body

pytestmark = pytest.mark.anyio


def settings():
    return config.load_settings(None)


async def call(handler, fn, *args):
    async with client_for(handler) as http:
        return await fn(http, settings(), *args)


def respond(status=200, json=None, content=None, headers=None):
    def handler(request):
        if content is not None:
            return httpx.Response(status, content=content, headers=headers)
        return httpx.Response(status, json=json, headers=headers)

    return handler


async def test_get_plot_parses():
    plot = await call(Upstreams(), clients.get_plot, PLOT_ID)
    assert plot.id == PLOT_ID and plot.crop_id == "tomato" and plot.soil_id == "loam"
    assert plot.planting_date == date(2026, 8, 10)
    assert (plot.area_m2, plot.row_spacing_m, plot.emitter_spacing_m, plot.lat, plot.lon) == (1000, 1.5, 0.4, 31.25, 34.79)


async def test_plot_404_is_not_found():
    with pytest.raises(clients.PlotNotFound):
        await call(Upstreams(), clients.get_plot, "f" * 36)


async def test_plot_id_is_one_encoded_segment():
    up = Upstreams()
    with pytest.raises(clients.PlotNotFound):
        await call(up, clients.get_plot, "../farms?x")
    assert up.requests[0].url.raw_path == b"/v1/plots/..%2Ffarms%3Fx"


async def test_registry_500_is_upstream():
    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(respond(500, {}), clients.get_plot, PLOT_ID)
    assert exc.value.service == "registry-service"
    assert exc.value.detail.startswith("registry-service unavailable")


async def test_registry_timeout_is_upstream():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(handler, clients.get_plot, PLOT_ID)
    assert exc.value.service == "registry-service"


@pytest.mark.parametrize("fn, handler", [
    (clients.get_plot, respond(content=b"<html>")),
    (clients.get_plot, respond(json=plot_body(area_m2=0))),
    (clients.get_plot, respond(json=plot_body(planting_date="2026-13-01"))),
    (clients.get_plot, respond(json={k: v for k, v in plot_body().items() if k != "lat"})),
    (clients.get_emitter_flow, respond(json={"id": "x", "flow_lph": 0})),
    (clients.get_emitter_flow, respond(json={"id": "x"})),
    (clients.get_soil_water, respond(json={"id": "x", "available_water_mm_per_m": "175"})),
])
async def test_registry_bad_body_is_upstream(fn, handler):
    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(handler, fn, "x")
    assert exc.value.service == "registry-service"


async def test_soil_and_emitter():
    assert await call(respond(json=SOIL), clients.get_soil_water, "loam") == 175
    assert await call(respond(json=EMITTER), clients.get_emitter_flow, "dripnet-pc-1.0") == 1.0


async def test_get_forecast_parses():
    up = Upstreams()
    forecast = await call(up, clients.get_forecast, 31.25, 34.79, 7)
    params = up.requests[0].url.params
    assert (params["lat"], params["lon"], params["days"]) == ("31.25", "34.79", "7")
    assert len(forecast.days) == 7
    assert forecast.days[0] == WeatherDay(TODAY, 6.0, 0.0)
    assert forecast.stale is False and forecast.fetched_at == "2026-11-17T06:00:00Z"


def _broken(problem):
    body = copy.deepcopy(forecast_body(7))
    if problem == "null_et0":
        body["days"][2]["et0_mm"] = None
    elif problem == "missing_day":
        body["days"].pop()
    elif problem == "extra_day":
        body["days"].append({"date": "2026-11-24", "et0_mm": 1.0, "rain_mm": 0.0})
    elif problem == "gap_in_dates":
        body["days"][3]["date"] = "2026-11-30"
    elif problem == "negative_rain":
        body["days"][0]["rain_mm"] = -1.0
    elif problem == "string_number":
        body["days"][0]["et0_mm"] = "6.0"
    elif problem == "bool_number":
        body["days"][0]["rain_mm"] = False
    elif problem == "no_stale":
        del body["stale"]
    elif problem == "no_days":
        del body["days"]
    return body


@pytest.mark.parametrize("problem", ["null_et0", "missing_day", "extra_day", "gap_in_dates", "negative_rain",
                                     "string_number", "bool_number", "no_stale", "no_days"])
async def test_bad_forecast_is_upstream_error(problem):
    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(respond(json=_broken(problem)), clients.get_forecast, 31.25, 34.79, 7)
    assert exc.value.service == "weather-service"


async def test_weather_503_keeps_retry_after():
    up = Upstreams()
    up.weather_down = True
    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(up, clients.get_forecast, 31.25, 34.79, 7)
    assert exc.value.service == "weather-service"
    assert exc.value.retry_after == "60"


async def test_weather_down_is_upstream():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(clients.UpstreamUnavailable) as exc:
        await call(handler, clients.get_forecast, 31.25, 34.79, 7)
    assert exc.value.service == "weather-service" and exc.value.retry_after is None


async def test_timeouts_come_from_settings():
    up = Upstreams()
    await call(up, clients.get_plot, PLOT_ID)
    await call(up, clients.get_forecast, 31.25, 34.79, 7)
    assert up.requests[0].extensions["timeout"]["read"] == 5
    assert up.requests[1].extensions["timeout"]["read"] == 20
