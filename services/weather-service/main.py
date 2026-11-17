import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request

import config

try:
    config.get_settings()
except config.ConfigError as exc:
    sys.exit(f"weather-service: {exc}")

import httpx  # noqa: E402

import problems  # noqa: E402
import provider  # noqa: E402
from forecast import MAX_DAYS, Forecaster, Unavailable  # noqa: E402
from problems import ProblemError  # noqa: E402

SOURCE = "open-meteo"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = config.get_settings()
    async with httpx.AsyncClient() as http:
        app.state.forecaster = Forecaster(
            fetch=lambda lat, lon: provider.fetch_daily(http, settings, lat, lon),
            settings=settings,
        )
        yield


app = FastAPI(title="AgroPilot weather-service", version="0.1.0", lifespan=lifespan)
problems.install(app)


def get_forecaster(request: Request) -> Forecaster:
    return request.app.state.forecaster


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/forecast")
async def get_forecast(
    forecaster: Annotated[Forecaster, Depends(get_forecaster)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    days: Annotated[int, Query(ge=1, le=MAX_DAYS)],
) -> dict:
    try:
        answer = await forecaster.get(lat, lon, days)
    except Unavailable:
        raise ProblemError(
            503,
            "Weather provider unavailable and no recent forecast for this location",
            {"Retry-After": str(config.get_settings().retry_after_s)},
        ) from None
    return {
        "lat": lat,
        "lon": lon,
        "source": SOURCE,
        "fetched_at": answer.fetched_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stale": answer.stale,
        "days": [
            {"date": day.date.isoformat(), "et0_mm": day.et0_mm, "rain_mm": day.rain_mm} for day in answer.days
        ],
    }
