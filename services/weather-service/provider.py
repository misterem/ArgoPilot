"""Open-Meteo client: one call, strictly validated.

This is the only module that knows Open-Meteo's URL parameters and field names. Anything other than
a complete, well-formed answer raises ProviderError; a day is never patched or defaulted (FR-2.8).
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from config import Settings

MAX_UTC_OFFSET_SECONDS = 18 * 3600  # the widest real offsets are -12 h / +14 h

# One more than the 7 days the API serves, so a forecast up to 24 h old still covers today + 6 days.
FETCH_DAYS = 8

_ET0 = "et0_fao_evapotranspiration"  # mm/day, FAO-56 Penman-Monteith reference ET (grass)
_RAIN = "precipitation_sum"  # mm/day, rain + showers + snowfall as water


@dataclass(frozen=True)
class Day:
    date: date
    et0_mm: float
    rain_mm: float


@dataclass(frozen=True)
class ProviderForecast:
    days: tuple[Day, ...]
    utc_offset_seconds: int


class ProviderError(Exception):
    pass


async def fetch_daily(client: httpx.AsyncClient, settings: Settings, lat: float, lon: float) -> ProviderForecast:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": f"{_ET0},{_RAIN}",
        "timezone": "auto",
        "forecast_days": FETCH_DAYS,
    }
    if settings.provider_api_key:
        params["apikey"] = settings.provider_api_key
    url = settings.provider_base_url.rstrip("/") + "/v1/forecast"
    try:
        response = await client.get(url, params=params, timeout=settings.provider_timeout_s)
    except httpx.HTTPError as exc:
        raise ProviderError(f"request failed: {type(exc).__name__}") from exc
    if not response.is_success:
        raise ProviderError(f"status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError("body is not JSON") from exc
    return _parse(body)


def _parse(body: object) -> ProviderForecast:
    if not isinstance(body, dict):
        raise ProviderError("body is not an object")
    offset = body.get("utc_offset_seconds")
    if not isinstance(offset, int) or isinstance(offset, bool) or abs(offset) > MAX_UTC_OFFSET_SECONDS:
        raise ProviderError("utc_offset_seconds missing, not an integer, or out of range")
    daily = body.get("daily")
    if not isinstance(daily, dict):
        raise ProviderError("daily missing")
    times, et0s, rains = (daily.get(key) for key in ("time", _ET0, _RAIN))
    if not all(isinstance(values, list) for values in (times, et0s, rains)):
        raise ProviderError("a daily field is missing")
    if not len(times) == len(et0s) == len(rains):
        raise ProviderError("daily fields have different lengths")
    if len(times) < FETCH_DAYS:
        raise ProviderError(f"{len(times)} days, need {FETCH_DAYS}")
    days = tuple(Day(_date(t), _amount(e), _amount(r)) for t, e, r in zip(times, et0s, rains))
    for prev, cur in zip(days, days[1:]):
        if cur.date - prev.date != timedelta(days=1):
            raise ProviderError("dates are not consecutive")
    return ProviderForecast(days=days, utc_offset_seconds=offset)


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ProviderError("date is not a string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ProviderError(f"bad date {value!r}") from exc


def _amount(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError(f"not a number: {value!r}")
    try:
        finite = math.isfinite(value)
    except OverflowError:  # an int too large for a float
        finite = False
    if not finite or value < 0:
        raise ProviderError(f"not a valid amount: {value!r}")
    return float(value)
