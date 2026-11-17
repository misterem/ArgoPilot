"""Test helpers: a fake Open-Meteo body and transport. No network."""

import copy
from datetime import date, timedelta

import httpx

START = date(2026, 11, 17)
ET0 = [3.1, 2.8, 4.0, 4.4, 3.9, 3.5, 3.0, 2.9]
RAIN = [0.0, 4.2, 0.0, 0.0, 1.5, 0.0, 0.0, 0.3]


def good_body(start: date = START, days: int = 8) -> dict:
    return {
        "latitude": 31.25,
        "longitude": 34.75,
        "utc_offset_seconds": 7200,
        "timezone": "Asia/Jerusalem",
        "daily_units": {"time": "iso8601", "et0_fao_evapotranspiration": "mm", "precipitation_sum": "mm"},
        "daily": {
            "time": [(start + timedelta(days=i)).isoformat() for i in range(days)],
            "et0_fao_evapotranspiration": ET0[:days],
            "precipitation_sum": RAIN[:days],
        },
    }


def body_with(**changes) -> dict:
    body = copy.deepcopy(good_body())
    for key, value in changes.items():
        body["daily"][key] = value
    return body


def transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def json_handler(body, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return handler
