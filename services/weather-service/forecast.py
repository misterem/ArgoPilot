"""Forecasts per 0.1° grid cell: in-memory cache, freshness, retries, stale fallback, single flight.

Rules (see README):
- A cell is cut at 0.1° steps; the provider is always asked for the cell centre.
- Fresh (younger than FORECAST_FRESH_HOURS) and covering the request: answered from memory, no provider call.
- Otherwise one fetch cycle per cell at a time: 1 attempt + PROVIDER_RETRIES retries. Requests that arrive
  while a cycle is in flight wait for it and share its outcome.
- After a failed cycle: the cell's last forecast if it is at most FORECAST_MAX_STALE_HOURS old and still
  covers the request (stale), else Unavailable. Failures are not remembered: the next request tries again.
"""

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from config import Settings
from provider import Day, ProviderError, ProviderForecast

MAX_DAYS = 7
_STEP = Decimal("0.1")

Cell = tuple[Decimal, Decimal]


def _floor_tenth(value: float, top: int) -> Decimal:
    tenths = math.floor(Decimal(repr(value)) * 10)
    return min(Decimal(tenths) * _STEP, Decimal(top) - _STEP)  # 90 / 180 fall in the last cell


def cell_of(lat: float, lon: float) -> Cell:
    return _floor_tenth(lat, 90), _floor_tenth(lon, 180)


def cell_centre(cell: Cell) -> tuple[float, float]:
    half = _STEP / 2
    return float(cell[0] + half), float(cell[1] + half)


@dataclass(frozen=True)
class Answer:
    days: tuple[Day, ...]
    fetched_at: datetime
    stale: bool


class Unavailable(Exception):
    pass


@dataclass(frozen=True)
class _Entry:
    forecast: ProviderForecast
    fetched_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Forecaster:
    def __init__(
        self,
        fetch: Callable[[float, float], Awaitable[ProviderForecast]],
        settings: Settings,
        now: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._fetch = fetch
        self._settings = settings
        self._now = now
        self._sleep = sleep
        self._entries: dict[Cell, _Entry] = {}
        self._inflight: dict[Cell, asyncio.Task[bool]] = {}

    async def get(self, lat: float, lon: float, days: int) -> Answer:
        cell = cell_of(lat, lon)
        entry = self._entries.get(cell)
        if entry is not None and self._is_fresh(entry):
            selected = self._select(entry, days)
            if selected is not None:
                return Answer(selected, entry.fetched_at, stale=False)

        task = self._inflight.get(cell)
        if task is None:
            task = asyncio.create_task(self._cycle(cell))
            self._inflight[cell] = task
            task.add_done_callback(lambda _: self._inflight.pop(cell, None))
        succeeded = await asyncio.shield(task)

        entry = self._entries.get(cell)
        if entry is None:
            raise Unavailable
        selected = self._select(entry, days)
        if succeeded and selected is not None:
            return Answer(selected, entry.fetched_at, stale=False)
        if selected is not None and self._now() - entry.fetched_at <= self._hours(self._settings.forecast_max_stale_hours):
            return Answer(selected, entry.fetched_at, stale=True)
        raise Unavailable

    async def _cycle(self, cell: Cell) -> bool:
        """Fetch with retries; store and return True on success. A failure leaves the entry untouched."""
        attempts = 1 + self._settings.provider_retries
        for attempt in range(attempts):
            if attempt:
                await self._sleep(self._settings.provider_retry_backoff_s)
            try:
                forecast = await self._fetch(*cell_centre(cell))
            except ProviderError:
                continue
            entry = _Entry(forecast, self._now())
            if self._select(entry, MAX_DAYS) is None:
                continue  # doesn't cover today + 6: a failed attempt, never a partial answer
            self._entries[cell] = entry
            return True
        return False

    def _is_fresh(self, entry: _Entry) -> bool:
        return self._now() - entry.fetched_at < self._hours(self._settings.forecast_fresh_hours)

    def _select(self, entry: _Entry, days: int) -> tuple[Day, ...] | None:
        """The days today … today + days − 1 (local to the point), or None if the entry lacks any of them."""
        today = self._local_today(entry)
        by_date = {day.date: day for day in entry.forecast.days}
        wanted = [today + timedelta(days=i) for i in range(days)]
        if not all(d in by_date for d in wanted):
            return None
        return tuple(by_date[d] for d in wanted)

    def _local_today(self, entry: _Entry) -> date:
        return (self._now() + timedelta(seconds=entry.forecast.utc_offset_seconds)).date()

    @staticmethod
    def _hours(value: float) -> timedelta:
        return timedelta(hours=value)
