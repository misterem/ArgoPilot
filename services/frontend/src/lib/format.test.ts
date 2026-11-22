import { describe, expect, it } from "vitest";

import {
  formatAge,
  formatClock,
  formatDayLong,
  formatDayShort,
  formatDuration,
  formatLitres,
  formatMm,
  formatWeekday,
} from "./format";

describe("formatDuration", () => {
  it.each([
    [38, "38 minutes"],
    [1, "1 minute"],
    [59, "59 minutes"],
    [60, "1 h"],
    [65, "1 h 05 min"],
    [113, "1 h 53 min"],
    [120, "2 h"],
    [1500, "25 h"],
  ])("%i → %s", (minutes, text) => expect(formatDuration(minutes)).toBe(text));
});

describe("formatClock", () => {
  it.each([
    [113, "1:53"],
    [41, "0:41"],
    [60, "1:00"],
    [1500, "25:00"],
  ])("%i → %s", (minutes, text) => expect(formatClock(minutes)).toBe(text));
});

describe("numbers and dates", () => {
  it("litres use a thousands separator", () => {
    expect(formatLitres(3128)).toBe("3,128");
    expect(formatLitres(650)).toBe("650");
  });
  it("mm keep at most one decimal", () => {
    expect(formatMm(9)).toBe("9");
    expect(formatMm(3.13)).toBe("3.1");
    expect(formatMm(0.65)).toBe("0.7");
  });
  it("plan dates are plain dates, never shifted by the time zone", () => {
    expect(formatDayShort("2026-11-18")).toBe("Wed 18 Nov");
    expect(formatWeekday("2026-11-19")).toBe("Thu");
    expect(formatDayLong("2026-11-19")).toBe("Thursday 19 November");
  });
  it("forecast age", () => {
    expect(formatAge("2026-11-17T06:00:00Z", new Date("2026-11-17T17:10:00Z"))).toBe("11 h");
    expect(formatAge("2026-11-17T06:00:00Z", new Date("2026-11-17T06:35:00Z"))).toBe("35 min");
    expect(formatAge("2026-11-17T06:00:00Z", new Date("2026-11-17T06:00:20Z"))).toBe("1 min");
  });
});
