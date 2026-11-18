"""The irrigation engine: pure functions, no I/O. Every number in a plan comes from here.

The method is written out in the irrigation-calc-reference skill ("AgroPilot planner method"). In short,
following FAO-56 with the choices made for AgroPilot:
- Kc from the crop curve (Eq. 66), ETc = Kc × ET0 (Eq. 58).
- Bucket TAW = available water × root depth (Eq. 82), RAW = p × TAW (Eq. 83).
- This morning the bucket is at the threshold (depletion Dr = RAW).
- Each day: effective rain (ignored below 0.2 × ET0) refills first; if the day's use would push depletion
  past RAW, irrigate just enough to end the day at RAW ("top up to the threshold").
- Net depth → litres → drip run time; no efficiency factor.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from crops import Crop

TOLERANCE_MM = 1e-9  # float noise: landing "exactly" on the threshold is not crossing it
_RAIN_IGNORED_BELOW = 0.2  # × ET0 (FAO-56 Ch. 8)


@dataclass(frozen=True)
class Field:
    planting_date: date
    area_m2: float
    row_spacing_m: float
    emitter_spacing_m: float
    emitter_flow_lph: float
    available_water_mm_per_m: float


@dataclass(frozen=True)
class WeatherDay:
    date: date
    et0_mm: float
    rain_mm: float


@dataclass(frozen=True)
class PlanDay:
    date: date
    et0_mm: float
    rain_mm: float
    kc: float
    etc_mm: float
    irrigation_mm: float
    litres: int
    run_minutes: int
    bucket_end_mm: float


@dataclass(frozen=True)
class Plan:
    season_end: date
    bucket_capacity_mm: float
    threshold_mm: float
    days: tuple[PlanDay, ...]


class SeasonError(Exception):
    pass


def round_half_up(x: float, ndigits: int = 0) -> float:
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-ndigits), rounding=ROUND_HALF_UP))


def kc_on_day(crop: Crop, i: int) -> float:
    """Kc on day i of the season (1-based), FAO-56 Eq. 66."""
    ini, dev, mid, late = crop.stages
    if i <= ini:
        return crop.kc_ini
    if i <= ini + dev:
        return crop.kc_ini + (i - ini) / dev * (crop.kc_mid - crop.kc_ini)
    if i <= ini + dev + mid:
        return crop.kc_mid
    return crop.kc_mid + (i - ini - dev - mid) / late * (crop.kc_end - crop.kc_mid)


def make_plan(crop: Crop, field: Field, weather: Sequence[WeatherDay]) -> Plan:
    season_end = field.planting_date + timedelta(days=crop.season_length - 1)
    today = weather[0].date
    first_day = (today - field.planting_date).days + 1
    if first_day < 1:
        raise SeasonError(f"Season has not started (planting date {field.planting_date.isoformat()}).")
    if first_day > crop.season_length:
        raise SeasonError(
            f"Season ended on {season_end.isoformat()} (day {crop.season_length} of {crop.season_length}); "
            "update the planting date."
        )

    taw = field.available_water_mm_per_m * crop.root_depth_m
    raw = crop.p * taw
    emitters = field.area_m2 / (field.row_spacing_m * field.emitter_spacing_m)
    system_lph = emitters * field.emitter_flow_lph

    depletion = raw  # this morning the bucket is at the threshold
    rows = []
    for day in weather:
        if day.date > season_end:
            break  # truncate: no rows after the season
        kc = kc_on_day(crop, (day.date - field.planting_date).days + 1)
        etc = kc * day.et0_mm
        rain = day.rain_mm if day.rain_mm >= _RAIN_IGNORED_BELOW * day.et0_mm - TOLERANCE_MM else 0.0
        start = max(0.0, depletion - rain)  # rain beyond an empty bucket drains
        need = start + etc - raw
        if need > TOLERANCE_MM:
            irrigation = need
            depletion = raw
        else:
            irrigation = 0.0
            depletion = min(start + etc, taw)
        litres = irrigation * field.area_m2
        rows.append(
            PlanDay(
                date=day.date,
                et0_mm=day.et0_mm,
                rain_mm=day.rain_mm,
                kc=kc,
                etc_mm=etc,
                irrigation_mm=irrigation,
                litres=int(round_half_up(litres)),
                run_minutes=int(round_half_up(litres / system_lph * 60)),
                bucket_end_mm=taw - depletion,
            )
        )
    return Plan(season_end=season_end, bucket_capacity_mm=taw, threshold_mm=taw - raw, days=tuple(rows))
