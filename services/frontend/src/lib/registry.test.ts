import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPlot } from "./registry";

describe("getPlot", () => {
  beforeEach(() => {
    vi.stubEnv("REGISTRY_URL", "http://registry.test");
    vi.stubEnv("WEATHER_URL", "http://weather.test");
    vi.stubEnv("PLANNER_URL", "http://planner.test");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it.each([".", "..", ""])("id %j is not_found without calling the registry", async (id) => {
    const fetch = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", fetch);
    expect(await getPlot(id)).toEqual({ ok: false, error: { kind: "not_found" } });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("a list where one plot was expected is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json([{ id: "x" }])));
    expect(await getPlot("p")).toEqual({ ok: false, error: { kind: "unavailable" } });
  });
});
