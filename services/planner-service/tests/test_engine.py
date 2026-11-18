from dataclasses import replace
from datetime import date, timedelta

import pytest

from crops import CROPS
from engine import Field, SeasonError, WeatherDay, kc_on_day, make_plan, round_half_up

TOMATO, PEPPER = CROPS["tomato"], CROPS["bell-pepper"]
TODAY = date(2026, 11, 17)
BASE = Field(TODAY - timedelta(days=99), 1000, 1.5, 0.4, 1.0, 175)  # today is day 100 (mid-season), loam


def field(**changes):
    return replace(BASE, **changes)


def days(*rows):
    return [WeatherDay(TODAY + timedelta(days=n), et0, rain) for n, (et0, rain) in enumerate(rows)]


def test_crop_table():
    assert TOMATO.season_length == 145
    assert PEPPER.season_length == 125
    assert (TOMATO.kc_ini, TOMATO.kc_mid, TOMATO.kc_end, TOMATO.root_depth_m, TOMATO.p) == (0.6, 1.15, 0.8, 0.7, 0.4)
    assert (PEPPER.kc_ini, PEPPER.kc_mid, PEPPER.kc_end, PEPPER.root_depth_m, PEPPER.p) == (0.6, 1.05, 0.9, 0.5, 0.3)


def test_kc_curve_tomato():
    assert kc_on_day(TOMATO, 1) == 0.6
    assert kc_on_day(TOMATO, 30) == 0.6
    assert kc_on_day(TOMATO, 50) == pytest.approx(0.875)
    assert kc_on_day(TOMATO, 70) == pytest.approx(1.15)
    assert kc_on_day(TOMATO, 100) == 1.15
    assert kc_on_day(TOMATO, 130) == pytest.approx(0.975)
    assert kc_on_day(TOMATO, 145) == pytest.approx(0.8)


def test_kc_curve_skill_case_1():
    crop = replace(TOMATO, kc_mid=1.2117, kc_end=0.8617)
    assert kc_on_day(crop, 50) == pytest.approx(0.9059, abs=1e-4)
    assert kc_on_day(crop, 130) == pytest.approx(1.0367, abs=1e-4)


def test_spec_example_248_minutes():
    plan = make_plan(TOMATO, field(), days((6.0, 0.0)))
    d = plan.days[0]
    assert d.kc == 1.15
    assert d.etc_mm == pytest.approx(6.9)
    assert d.irrigation_mm == pytest.approx(6.9)
    assert (d.litres, d.run_minutes) == (6900, 248)
    assert plan.bucket_capacity_mm == pytest.approx(122.5)
    assert plan.threshold_mm == pytest.approx(73.5)
    assert d.bucket_end_mm == pytest.approx(73.5)


def test_design_worked_case_three_days():
    plan = make_plan(TOMATO, field(), days((6.0, 0.0), (5.0, 12.0), (6.0, 0.5)))
    assert [(d.litres, d.run_minutes) for d in plan.days] == [(6900, 248), (0, 0), (650, 23)]
    assert [round(d.bucket_end_mm, 2) for d in plan.days] == [73.5, 79.75, 73.5]
    assert plan.days[1].irrigation_mm == 0
    assert plan.days[2].irrigation_mm == pytest.approx(0.65)


def test_small_rain_is_ignored():
    d = make_plan(TOMATO, field(), days((6.0, 1.0))).days[0]
    assert d.irrigation_mm == pytest.approx(6.9)


def test_rain_at_one_fifth_of_et0_counts():
    d = make_plan(TOMATO, field(), days((6.0, 1.2))).days[0]
    assert d.irrigation_mm == pytest.approx(6.9 - 1.2)


def test_heavy_rain_drains_and_bucket_stays_full():
    d = make_plan(TOMATO, field(), days((6.0, 200.0))).days[0]
    assert d.irrigation_mm == 0 and d.run_minutes == 0
    assert d.bucket_end_mm == pytest.approx(122.5 - 6.9)


def test_exactly_at_threshold_does_not_irrigate():
    d = make_plan(TOMATO, field(), days((5.0, 5.75))).days[0]  # ETc 5.75 == rain: ends exactly at the threshold
    assert d.irrigation_mm == 0 and d.litres == 0 and d.run_minutes == 0


@pytest.mark.parametrize("noise", [1e-12, -1e-12])
def test_float_noise_at_threshold_does_not_irrigate(noise):
    d = make_plan(TOMATO, field(), days((5.0, 5.75 + noise))).days[0]
    assert d.irrigation_mm == 0


def test_pepper_bucket_on_sand():
    plan = make_plan(PEPPER, field(available_water_mm_per_m=83), days((6.0, 0.0)))
    assert plan.bucket_capacity_mm == pytest.approx(41.5)
    assert plan.threshold_mm == pytest.approx(29.05)
    assert plan.days[0].irrigation_mm == pytest.approx(1.05 * 6.0)


def test_truncates_at_season_end():
    plan = make_plan(TOMATO, field(planting_date=TODAY - timedelta(days=143)), days(*[(5.0, 0.0)] * 7))
    assert len(plan.days) == 2
    assert plan.season_end == TODAY + timedelta(days=1)
    assert plan.days[-1].date == plan.season_end


def test_season_ended_raises():
    with pytest.raises(SeasonError, match=r"^Season ended on 2026-11-16 \(day 145 of 145\); update the planting date\.$"):
        make_plan(TOMATO, field(planting_date=TODAY - timedelta(days=145)), days((5.0, 0.0)))


def test_planting_after_today_raises():
    with pytest.raises(SeasonError, match=r"^Season has not started \(planting date 2026-11-18\)\.$"):
        make_plan(TOMATO, field(planting_date=TODAY + timedelta(days=1)), days((5.0, 0.0)))


def test_planting_day_is_day_one():
    plan = make_plan(TOMATO, field(planting_date=TODAY), days((5.0, 0.0)))
    assert plan.days[0].kc == 0.6
    assert plan.season_end == TODAY + timedelta(days=144)


def test_run_longer_than_a_day_is_reported():
    d = make_plan(TOMATO, field(row_spacing_m=2.0, emitter_spacing_m=1.0, emitter_flow_lph=0.6), days((10.0, 0.0))).days[0]
    assert d.run_minutes > 1440  # 11.5 mm at 0.3 mm/h ≈ 2300 min, not capped


def test_round_half_up():
    assert round_half_up(23.5) == 24
    assert round_half_up(22.5) == 23
    assert round_half_up(0.125, 2) == 0.13
