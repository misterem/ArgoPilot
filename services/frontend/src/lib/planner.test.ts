import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPlan } from "./planner";

const PLAN = { plot_id: "p", days: [{ date: "2026-11-18" }] };

function stubFetch(impl: (url: string) => Promise<Response>) {
  const fn = vi.fn(impl);
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("getPlan", () => {
  beforeEach(() => {
    vi.stubEnv("REGISTRY_URL", "http://registry.test");
    vi.stubEnv("WEATHER_URL", "http://weather.test");
    vi.stubEnv("PLANNER_URL", "http://planner.test/");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("returns the plan", async () => {
    const fetch = stubFetch(async () => Response.json(PLAN));
    expect(await getPlan("p")).toEqual({ ok: true, data: PLAN });
    expect(fetch.mock.calls[0][0]).toBe("http://planner.test/v1/plots/p/plan?days=7");
  });

  it("keeps the problem's status, code and detail", async () => {
    stubFetch(async () =>
      new Response(JSON.stringify({ status: 503, code: "UPSTREAM_UNAVAILABLE", detail: "weather-service unavailable: x" }), {
        status: 503, headers: { "content-type": "application/problem+json" },
      }),
    );
    expect(await getPlan("p")).toEqual({
      ok: false, error: { kind: "problem", status: 503, code: "UPSTREAM_UNAVAILABLE", detail: "weather-service unavailable: x" },
    });
  });

  it("404 is not_found", async () => {
    stubFetch(async () => new Response(JSON.stringify({ status: 404, code: "NOT_FOUND", detail: "Plot not found" }), { status: 404 }));
    expect(await getPlan("p")).toEqual({ ok: false, error: { kind: "not_found" } });
  });

  it("network failure or timeout is unavailable", async () => {
    stubFetch(async () => { throw new DOMException("timed out", "TimeoutError"); });
    expect(await getPlan("p")).toEqual({ ok: false, error: { kind: "unavailable" } });
  });

  it("a non-JSON error page is unavailable", async () => {
    stubFetch(async () => new Response("<html>bad gateway</html>", { status: 502 }));
    expect(await getPlan("p")).toEqual({ ok: false, error: { kind: "unavailable" } });
  });

  it("ids stay one path segment", async () => {
    const fetch = stubFetch(async () => Response.json(PLAN));
    await getPlan("../x?y");
    expect(fetch.mock.calls[0][0]).toBe("http://planner.test/v1/plots/..%2Fx%3Fy/plan?days=7");
  });

  it.each([".", "..", ""])("id %j is not_found without calling the planner (URL parsing would collapse it)", async (id) => {
    const fetch = stubFetch(async () => Response.json(PLAN));
    expect(await getPlan(id)).toEqual({ ok: false, error: { kind: "not_found" } });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([{}, { days: [] }, { days: "x" }, []])("a 200 without plan days is unavailable: %j", async (body) => {
    stubFetch(async () => Response.json(body));
    expect(await getPlan("p")).toEqual({ ok: false, error: { kind: "unavailable" } });
  });
});
