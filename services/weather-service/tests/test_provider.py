import copy
import json
from datetime import date

import httpx
import pytest

import config
import provider
from fakes import RAIN, body_with, good_body, json_handler, transport

pytestmark = pytest.mark.anyio


def settings(**overrides):
    return config.load_settings(None).model_copy(update=overrides)


async def fetch(handler, **overrides):
    async with httpx.AsyncClient(transport=transport(handler)) as client:
        return await provider.fetch_daily(client, settings(**overrides), 31.25, 34.75)


async def test_parses_good_body():
    result = await fetch(json_handler(good_body()))
    assert len(result.days) == provider.FETCH_DAYS == 8
    assert result.days[0] == provider.Day(date(2026, 11, 17), 3.1, 0.0)
    assert result.days[1].rain_mm == 4.2
    assert result.utc_offset_seconds == 7200


async def test_sends_expected_query():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=good_body())

    await fetch(handler)
    url = seen[0].url
    assert str(url).startswith("https://provider.test/v1/forecast?")
    assert url.params["latitude"] == "31.25"
    assert url.params["longitude"] == "34.75"
    assert url.params["daily"] == "et0_fao_evapotranspiration,precipitation_sum"
    assert url.params["timezone"] == "auto"
    assert url.params["forecast_days"] == "8"
    assert "apikey" not in url.params


async def test_sends_apikey_when_set():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=good_body())

    await fetch(handler, provider_api_key="k")
    assert seen[0].url.params["apikey"] == "k"


async def test_timeout_is_failure():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(provider.ProviderError):
        await fetch(handler)


async def test_connection_error_is_failure():
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(provider.ProviderError):
        await fetch(handler)


@pytest.mark.parametrize("status", [400, 429, 500, 503])
async def test_error_status_is_failure(status):
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler({"error": True, "reason": "x"}, status))


async def test_non_json_is_failure():
    with pytest.raises(provider.ProviderError):
        await fetch(lambda request: httpx.Response(200, text="<html>"))


@pytest.mark.parametrize("path", [("daily",), ("daily", "time"), ("daily", "et0_fao_evapotranspiration"),
                                  ("daily", "precipitation_sum"), ("utc_offset_seconds",)])
async def test_missing_field_is_failure(path):
    body = copy.deepcopy(good_body())
    target = body
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body))


async def test_body_not_an_object_is_failure():
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler([1, 2, 3]))


async def test_null_value_is_failure():
    et0 = good_body()["daily"]["et0_fao_evapotranspiration"]
    et0[3] = None
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(et0_fao_evapotranspiration=et0)))


async def test_null_rain_is_failure():
    rain = list(RAIN)
    rain[0] = None
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(precipitation_sum=rain)))


@pytest.mark.parametrize("bad", ["3.1", True, [3.1], float("nan"), float("inf")])
async def test_non_number_is_failure(bad):
    et0 = good_body()["daily"]["et0_fao_evapotranspiration"]
    et0[0] = bad
    content = json.dumps(body_with(et0_fao_evapotranspiration=et0))  # NaN/Infinity tokens, as a lenient server might send
    with pytest.raises(provider.ProviderError):
        await fetch(lambda request: httpx.Response(200, content=content.encode()))


async def test_negative_value_is_failure():
    rain = list(RAIN)
    rain[2] = -1.0
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(precipitation_sum=rain)))


async def test_mismatched_lengths_is_failure():
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(precipitation_sum=RAIN[:7])))


async def test_too_few_days_is_failure():
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(good_body(days=7)))


async def test_unparseable_date_is_failure():
    times = good_body()["daily"]["time"]
    times[2] = "2026-11-xx"
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(time=times)))


async def test_non_consecutive_dates_is_failure():
    times = good_body()["daily"]["time"]
    times[4] = "2026-11-30"
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body_with(time=times)))


async def test_huge_integer_is_failure():
    content = json.dumps(good_body()).replace('"precipitation_sum": [0.0', '"precipitation_sum": [' + "9" * 400, 1)
    with pytest.raises(provider.ProviderError):
        await fetch(lambda request: httpx.Response(200, content=content.encode()))


@pytest.mark.parametrize("offset", [10**12, -10**12, 18 * 3600 + 1])
async def test_absurd_utc_offset_is_failure(offset):
    body = good_body()
    body["utc_offset_seconds"] = offset
    with pytest.raises(provider.ProviderError):
        await fetch(json_handler(body))
