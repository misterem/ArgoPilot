import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request

import config

try:
    config.get_settings()
except config.ConfigError as exc:
    sys.exit(f"planner-service: {exc}")

import httpx  # noqa: E402

import clients  # noqa: E402
import problems  # noqa: E402
from crops import CROPS  # noqa: E402
from engine import Field, Plan, SeasonError, make_plan, round_half_up  # noqa: E402
from problems import ProblemError  # noqa: E402

MAX_DAYS = 7


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient() as http:
        app.state.http = http
        yield


app = FastAPI(title="AgroPilot planner-service", version="0.1.0", lifespan=lifespan)
problems.install(app)


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/plots/{plot_id}/plan")
async def get_plan(
    plot_id: str,
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    days: Annotated[int, Query(ge=1, le=MAX_DAYS)] = MAX_DAYS,
) -> dict:
    settings = config.get_settings()
    try:
        plot = await clients.get_plot(http, settings, plot_id)
    except clients.PlotNotFound:
        raise ProblemError(404, "Plot not found") from None
    except clients.UpstreamUnavailable as exc:
        raise _upstream(exc) from None

    # Registry first, then weather: when both fail, the registry is named.
    results = await asyncio.gather(
        clients.get_soil_water(http, settings, plot.soil_id),
        clients.get_emitter_flow(http, settings, plot.emitter_id),
        clients.get_forecast(http, settings, plot.lat, plot.lon, days),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, clients.UpstreamUnavailable):
            raise _upstream(result)
        if isinstance(result, BaseException):
            raise result
    water_mm_per_m, flow_lph, forecast = results

    crop = CROPS.get(plot.crop_id)
    if crop is None:
        raise ProblemError(422, f"No crop parameters for '{plot.crop_id}'")
    field = Field(
        planting_date=plot.planting_date,
        area_m2=plot.area_m2,
        row_spacing_m=plot.row_spacing_m,
        emitter_spacing_m=plot.emitter_spacing_m,
        emitter_flow_lph=flow_lph,
        available_water_mm_per_m=water_mm_per_m,
    )
    try:
        plan = make_plan(crop, field, forecast.days)
    except SeasonError as exc:
        raise ProblemError(422, str(exc)) from None
    return _body(plot, plan, forecast)


def _upstream(exc: clients.UpstreamUnavailable) -> ProblemError:
    headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
    return ProblemError(503, exc.detail, headers, code="UPSTREAM_UNAVAILABLE")


def _mm(x: float) -> float:
    return round_half_up(x, 2)


def _body(plot: clients.Plot, plan: Plan, forecast: clients.Forecast) -> dict:
    return {
        "plot_id": plot.id,
        "crop_id": plot.crop_id,
        "planting_date": plot.planting_date.isoformat(),
        "season_end": plan.season_end.isoformat(),
        "bucket_capacity_mm": _mm(plan.bucket_capacity_mm),
        "threshold_mm": _mm(plan.threshold_mm),
        "fetched_at": forecast.fetched_at,
        "stale": forecast.stale,
        "days": [
            {
                "date": day.date.isoformat(),
                "et0_mm": _mm(day.et0_mm),
                "rain_mm": _mm(day.rain_mm),
                "kc": round_half_up(day.kc, 3),
                "etc_mm": _mm(day.etc_mm),
                "irrigation_mm": _mm(day.irrigation_mm),
                "litres": day.litres,
                "run_minutes": day.run_minutes,
                "bucket_end_mm": _mm(day.bucket_end_mm),
                "stale": forecast.stale,
            }
            for day in plan.days
        ],
    }
