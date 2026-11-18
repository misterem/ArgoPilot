import { describe, expect, it } from "vitest";

import { barHeights, describePlanError, gauge, heroSubline, seasonEndNote } from "./plan";
import type { Plan, PlanDay } from "./types";

function day(over: Partial<PlanDay> = {}): PlanDay {
  return {
    date: "2026-11-18", et0_mm: 2.72, rain_mm: 0, kc: 1.15, etc_mm: 3.13, irrigation_mm: 3.13,
    litres: 3128, run_minutes: 113, bucket_end_mm: 73.5, stale: false, ...over,
  };
}

function plan(over: Partial<Plan> = {}): Plan {
  return {
    plot_id: "p", crop_id: "tomato", planting_date: "2026-08-11", season_end: "2027-01-02",
    bucket_capacity_mm: 122.5, threshold_mm: 73.5, fetched_at: "2026-11-18T08:59:37Z", stale: false,
    days: Array.from({ length: 7 }, (_, i) => day({ date: `2026-11-${18 + i}` })), ...over,
  };
}

describe("describePlanError", () => {
  it("season ended shows the planner's text as it comes", () => {
    const detail = "Season ended on 2026-07-23 (day 145 of 145); update the planting date.";
    expect(describePlanError({ kind: "problem", status: 422, code: "VALIDATION", detail })).toEqual({
      title: "No plan: the season ended", text: detail,
    });
  });
  it("other 422s", () => {
    const detail = "No crop parameters for 'melon'";
    expect(describePlanError({ kind: "problem", status: 422, code: "VALIDATION", detail })).toEqual({
      title: "No plan for this plot", text: detail,
    });
  });
  it("names weather-service", () => {
    expect(describePlanError({ kind: "problem", status: 503, code: "UPSTREAM_UNAVAILABLE", detail: "weather-service unavailable: status 503" }))
      .toEqual({ title: "Weather service is not answering", text: "The plan needs the forecast. Try again in a minute." });
  });
  it("names registry-service", () => {
    expect(describePlanError({ kind: "problem", status: 503, code: "UPSTREAM_UNAVAILABLE", detail: "registry-service unavailable: x" }))
      .toEqual({ title: "Registry service is not answering", text: "The plan needs the plot's details. Try again in a minute." });
  });
  it("planner itself unreachable or broken", () => {
    const planner = { title: "Planner service is not answering", text: "Try again in a minute." };
    expect(describePlanError({ kind: "unavailable" })).toEqual(planner);
    expect(describePlanError({ kind: "problem", status: 500, code: "UNAVAILABLE", detail: "x" })).toEqual(planner);
  });
  it("404 becomes the not-found page", () => {
    expect(describePlanError({ kind: "not_found" })).toBe("not_found");
  });
});

describe("gauge", () => {
  it("fractions of the bucket", () => {
    const g = gauge(plan());
    expect(g.water).toBeCloseTo(0.6);
    expect(g.refill).toBeCloseTo(0.6);
  });
  it("clamps to 0..1", () => {
    const g = gauge(plan({ days: [day({ bucket_end_mm: 130 })] }));
    expect(g.water).toBe(1);
  });
});

describe("barHeights", () => {
  it("largest day is 1", () => expect(barHeights([113, 0, 140])).toEqual([113 / 140, 0, 1]));
  it("a week of zeros has no division by zero", () => expect(barHeights([0, 0, 0])).toEqual([0, 0, 0]));
});

describe("heroSubline", () => {
  it("irrigation day", () => expect(heroSubline(day())).toBe("3,128 litres through the drip line."));
  it("rain covers it", () =>
    expect(heroSubline(day({ run_minutes: 0, litres: 0, rain_mm: 9 }))).toBe("Rain and stored soil water cover today's use."));
  it("stored water covers it", () =>
    expect(heroSubline(day({ run_minutes: 0, litres: 0, rain_mm: 0 }))).toBe("Stored soil water covers today's use."));
});

describe("seasonEndNote", () => {
  it("plan stops at the season end", () => {
    const p = plan({ season_end: "2026-11-19", days: [day({ date: "2026-11-18" }), day({ date: "2026-11-19" })] });
    expect(seasonEndNote(p)).toBe("The season ends on Thu 19 Nov; the plan stops there.");
  });
  it("full week: no note", () => expect(seasonEndNote(plan())).toBeNull());
});
