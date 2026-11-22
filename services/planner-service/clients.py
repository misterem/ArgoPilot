"""Calls to registry-service and weather-service, with strict checks on what comes back.

Anything other than a complete, well-formed answer raises UpstreamUnavailable naming the service. Nothing is
defaulted: a missing number is an outage, never a zero (FR-2.8, FR-2.14).
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote

import httpx

from config import Settings
from engine import WeatherDay

REGISTRY = "registry-service"
WEATHER = "weather-service"


class PlotNotFound(Exception):
    pass


class UpstreamUnavailable(Exception):
    def __init__(self, service: str, reason: str, retry_after: str | None = None) -> None:
        super().__init__(f"{service} unavailable: {reason}")
        self.service = service
        self.reason = reason
        self.retry_after = retry_after

    @property
    def detail(self) -> str:
        return f"{self.service} unavailable: {self.reason}"


@dataclass(frozen=True)
class Plot:
    id: str
    crop_id: str
    planting_date: date
    soil_id: str
    emitter_id: str
    area_m2: float
    row_spacing_m: float
    emitter_spacing_m: float
    lat: float
    lon: float


@dataclass(frozen=True)
class Forecast:
    fetched_at: str
    stale: bool
    days: tuple[WeatherDay, ...]


async def get_plot(http: httpx.AsyncClient, settings: Settings, plot_id: str) -> Plot:
    body = await _get_json(http, REGISTRY, settings.registry_url, f"/v1/plots/{_segment(plot_id)}",
                           settings.registry_timeout_s, not_found=PlotNotFound)
    with _bad_body(REGISTRY):
        return Plot(
            id=_text(body, "id"),
            crop_id=_text(body, "crop_id"),
            planting_date=date.fromisoformat(_text(body, "planting_date")),
            soil_id=_text(body, "soil_id"),
            emitter_id=_text(body, "emitter_id"),
            area_m2=_positive(body, "area_m2"),
            row_spacing_m=_positive(body, "row_spacing_m"),
            emitter_spacing_m=_positive(body, "emitter_spacing_m"),
            lat=_number(body, "lat"),
            lon=_number(body, "lon"),
        )


async def get_soil_water(http: httpx.AsyncClient, settings: Settings, soil_id: str) -> float:
    body = await _get_json(http, REGISTRY, settings.registry_url, f"/v1/soils/{_segment(soil_id)}",
                           settings.registry_timeout_s)
    with _bad_body(REGISTRY):
        return _positive(body, "available_water_mm_per_m")


async def get_emitter_flow(http: httpx.AsyncClient, settings: Settings, emitter_id: str) -> float:
    body = await _get_json(http, REGISTRY, settings.registry_url, f"/v1/emitters/{_segment(emitter_id)}",
                           settings.registry_timeout_s)
    with _bad_body(REGISTRY):
        return _positive(body, "flow_lph")


async def get_forecast(http: httpx.AsyncClient, settings: Settings, lat: float, lon: float, days: int) -> Forecast:
    body = await _get_json(http, WEATHER, settings.weather_url, "/v1/forecast", settings.weather_timeout_s,
                           params={"lat": lat, "lon": lon, "days": days})
    with _bad_body(WEATHER):
        stale = body["stale"]
        if not isinstance(stale, bool):
            raise ValueError("stale is not a boolean")
        rows = body["days"]
        if not isinstance(rows, list) or len(rows) != days:
            raise ValueError(f"expected {days} days")
        parsed = tuple(
            WeatherDay(date.fromisoformat(_text(row, "date")), _amount(row, "et0_mm"), _amount(row, "rain_mm"))
            for row in rows
        )
        for prev, cur in zip(parsed, parsed[1:]):
            if cur.date - prev.date != timedelta(days=1):
                raise ValueError("dates are not consecutive")
        return Forecast(fetched_at=_text(body, "fetched_at"), stale=stale, days=parsed)


# --- helpers ---

def _segment(value: str) -> str:
    # One path segment: "/" and "?" are encoded by quote(); dots too, or httpx would collapse "." / ".."
    # and reach another route (e.g. the registry's plot list).
    return quote(value, safe="").replace(".", "%2E")


async def _get_json(http, service, base_url, path, timeout, params=None, not_found=None) -> dict:
    url = base_url.rstrip("/") + path
    try:
        response = await http.get(url, params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(service, f"request failed ({type(exc).__name__})") from exc
    if response.status_code == 404 and not_found is not None:
        raise not_found()
    if not response.is_success:
        raise UpstreamUnavailable(service, f"status {response.status_code}", response.headers.get("Retry-After"))
    try:
        body = response.json()
    except ValueError as exc:
        raise UpstreamUnavailable(service, "body is not JSON") from exc
    if not isinstance(body, dict):
        raise UpstreamUnavailable(service, "body is not an object")
    return body


class _bad_body:
    """Turns any parsing problem inside the block into UpstreamUnavailable for that service."""

    def __init__(self, service: str) -> None:
        self.service = service

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None and issubclass(exc_type, (KeyError, TypeError, ValueError, OverflowError)):
            raise UpstreamUnavailable(self.service, f"unexpected answer ({exc})") from exc
        return False


def _text(body: dict, key: str) -> str:
    value = body[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is not a string")
    return value


def _number(body: dict, key: str) -> float:
    value = body[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} is not a number")
    return float(value)


def _amount(body: dict, key: str) -> float:
    value = _number(body, key)
    if value < 0:
        raise ValueError(f"{key} is negative")
    return value


def _positive(body: dict, key: str) -> float:
    value = _number(body, key)
    if value <= 0:
        raise ValueError(f"{key} is not positive")
    return value
