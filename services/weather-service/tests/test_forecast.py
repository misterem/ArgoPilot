import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import config
from fakes import START, good_body
from forecast import Forecaster, Unavailable, cell_centre, cell_of
from provider import ProviderError, _parse

T0 = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)  # 08:00 local (+2h)


def forecast_from(start=START):
    return _parse(good_body(start))


class Clock:
    def __init__(self, at=T0):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, **kw):
        self.at += timedelta(**kw)


class FakeFetch:
    """Each call pops the next outcome: a ProviderForecast, or an exception to raise. Default: success."""

    def __init__(self, *outcomes, gate: asyncio.Event | None = None):
        self.outcomes = list(outcomes)
        self.calls: list[tuple[float, float]] = []
        self.gate = gate

    async def __call__(self, lat, lon):
        self.calls.append((lat, lon))
        if self.gate is not None:
            await self.gate.wait()
        outcome = self.outcomes.pop(0) if self.outcomes else forecast_from()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


FAIL = ProviderError("down")


class Sleeps:
    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)


def make(fetch, clock=None, sleep=None):
    return Forecaster(fetch=fetch, settings=config.load_settings(None), now=clock or Clock(), sleep=sleep or Sleeps())


# --- grid cells ---

def test_cell_same_cell():
    assert cell_of(31.25, 34.79) == cell_of(31.29, 34.71) == (Decimal("31.2"), Decimal("34.7"))


def test_cell_boundary():
    assert cell_of(31.3, 34.7) == (Decimal("31.3"), Decimal("34.7"))
    assert cell_of(0.3, 0.7) == (Decimal("0.3"), Decimal("0.7"))


def test_cell_negative():
    assert cell_of(-31.25, -0.01) == (Decimal("-31.3"), Decimal("-0.1"))


def test_cell_edges():
    assert cell_centre(cell_of(90, 180)) == (89.95, 179.95)
    assert cell_centre(cell_of(-90, -180)) == (-89.95, -179.95)


# --- cache and freshness ---

pytestmark_anyio = pytest.mark.anyio


@pytestmark_anyio
async def test_first_request_fetches_cell_centre():
    fetch = FakeFetch()
    answer = await make(fetch).get(31.25, 34.79, 7)
    assert fetch.calls == [(31.25, 34.75)]
    assert [d.date for d in answer.days] == [date(2026, 11, 17) + timedelta(days=i) for i in range(7)]
    assert answer.days[0].et0_mm == 3.1
    assert answer.stale is False
    assert answer.fetched_at == T0


@pytestmark_anyio
async def test_fresh_hit_does_not_fetch():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    await f.get(31.25, 34.79, 7)
    clock.advance(hours=2, minutes=59)
    answer = await f.get(31.21, 34.71, 7)
    assert len(fetch.calls) == 1
    assert answer.stale is False and answer.fetched_at == T0


@pytestmark_anyio
async def test_other_cell_fetches():
    fetch = FakeFetch()
    f = make(fetch)
    await f.get(31.25, 34.79, 7)
    await f.get(31.35, 34.79, 7)
    assert len(fetch.calls) == 2


@pytestmark_anyio
async def test_after_fresh_window_refetches():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    await f.get(31.25, 34.79, 7)
    clock.advance(hours=3)
    answer = await f.get(31.25, 34.79, 7)
    assert len(fetch.calls) == 2
    assert answer.fetched_at == T0 + timedelta(hours=3)


@pytestmark_anyio
async def test_days_slices_from_today():
    answer = await make(FakeFetch()).get(31.25, 34.79, 3)
    assert [d.date for d in answer.days] == [date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 19)]


@pytestmark_anyio
async def test_after_local_midnight_today_is_first():
    clock = Clock(datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc))  # 23:30 local
    fetch = FakeFetch()
    f = make(fetch, clock)
    await f.get(31.25, 34.79, 7)
    clock.advance(hours=1)  # 00:30 local, 2026-11-18
    answer = await f.get(31.25, 34.79, 7)
    assert len(fetch.calls) == 1
    assert answer.days[0].date == date(2026, 11, 18)
    assert len(answer.days) == 7


@pytestmark_anyio
async def test_answer_not_covering_today_plus_6_is_a_failed_attempt():
    # Provider's first day is two days ago (local): only 6 days from today. Treated as a failure and retried.
    fetch = FakeFetch(forecast_from(START - timedelta(days=2)), forecast_from())
    answer = await make(fetch).get(31.25, 34.79, 1)
    assert len(fetch.calls) == 2
    assert answer.days[0].date == START and answer.stale is False


# --- retries and failures ---

@pytestmark_anyio
async def test_retries_twice_then_succeeds():
    fetch, sleeps = FakeFetch(FAIL, FAIL), Sleeps()
    answer = await make(fetch, sleep=sleeps).get(31.25, 34.79, 7)
    assert len(fetch.calls) == 3
    assert answer.stale is False
    assert sleeps.calls == [0.5, 0.5]


@pytestmark_anyio
async def test_failure_without_entry_is_unavailable():
    fetch = FakeFetch(FAIL, FAIL, FAIL)
    with pytest.raises(Unavailable):
        await make(fetch).get(31.25, 34.79, 7)
    assert len(fetch.calls) == 3


@pytestmark_anyio
async def test_failure_serves_stale():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    first = await f.get(31.25, 34.79, 7)
    clock.advance(hours=4)
    fetch.outcomes = [FAIL, FAIL, FAIL]
    answer = await f.get(31.25, 34.79, 7)
    assert answer.stale is True
    assert answer.fetched_at == T0
    assert answer.days == first.days
    assert len(fetch.calls) == 4


@pytestmark_anyio
async def test_stale_at_exactly_24h_is_served():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    await f.get(31.25, 34.79, 7)
    clock.advance(hours=24)
    fetch.outcomes = [FAIL, FAIL, FAIL]
    answer = await f.get(31.25, 34.79, 7)
    assert answer.stale is True
    assert answer.days[0].date == date(2026, 11, 18) and len(answer.days) == 7


@pytestmark_anyio
async def test_stale_older_than_24h_is_unavailable():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    await f.get(31.25, 34.79, 7)
    clock.advance(hours=24, seconds=1)
    fetch.outcomes = [FAIL, FAIL, FAIL]
    with pytest.raises(Unavailable):
        await f.get(31.25, 34.79, 7)


@pytestmark_anyio
async def test_failure_does_not_touch_entry():
    fetch, clock = FakeFetch(), Clock()
    f = make(fetch, clock)
    first = await f.get(31.25, 34.79, 7)
    clock.advance(hours=4)
    fetch.outcomes = [FAIL] * 6
    await f.get(31.25, 34.79, 7)
    again = await f.get(31.25, 34.79, 7)
    assert again.stale is True and again.days == first.days and again.fetched_at == T0


@pytestmark_anyio
async def test_no_failure_memory():
    fetch = FakeFetch(*[FAIL] * 6)
    f = make(fetch)
    for _ in range(2):
        with pytest.raises(Unavailable):
            await f.get(31.25, 34.79, 7)
    assert len(fetch.calls) == 6


# --- single flight ---

@pytestmark_anyio
async def test_concurrent_requests_share_one_failed_cycle():
    gate = asyncio.Event()
    fetch = FakeFetch(*[FAIL] * 15, gate=gate)
    f = make(fetch)
    tasks = [asyncio.create_task(f.get(31.25, 34.79, 7)) for _ in range(5)]
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, Unavailable) for r in results)
    assert len(fetch.calls) == 3


@pytestmark_anyio
async def test_concurrent_requests_share_one_success():
    gate = asyncio.Event()
    fetch = FakeFetch(gate=gate)
    f = make(fetch)
    tasks = [asyncio.create_task(f.get(31.25, 34.79, d)) for d in (7, 7, 3, 1, 7)]
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks)
    assert len(fetch.calls) == 1
    assert [len(r.days) for r in results] == [7, 7, 3, 1, 7]


@pytestmark_anyio
async def test_fresh_hit_does_not_wait_for_inflight_other_cell():
    f = make(FakeFetch())
    await f.get(31.45, 34.79, 7)  # cell B now fresh
    gate = asyncio.Event()
    f._fetch = FakeFetch(gate=gate)
    blocked = asyncio.create_task(f.get(31.25, 34.79, 7))  # cell A, stuck in fetch
    await asyncio.sleep(0)
    answer = await asyncio.wait_for(f.get(31.45, 34.79, 7), timeout=1)
    assert answer.stale is False
    gate.set()
    await blocked
