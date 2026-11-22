import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getConfig } from "./config";

describe("getConfig", () => {
  beforeEach(() => {
    vi.stubEnv("REGISTRY_URL", "http://127.0.0.1:8000/");
    vi.stubEnv("WEATHER_URL", "http://127.0.0.1:8001");
    vi.stubEnv("PLANNER_URL", "http://127.0.0.1:8002");
  });
  afterEach(() => vi.unstubAllEnvs());

  it("returns the three URLs without a trailing slash", () => {
    expect(getConfig()).toEqual({
      registryUrl: "http://127.0.0.1:8000",
      weatherUrl: "http://127.0.0.1:8001",
      plannerUrl: "http://127.0.0.1:8002",
    });
  });

  it("names a missing variable", () => {
    vi.stubEnv("PLANNER_URL", undefined);
    expect(() => getConfig()).toThrow("PLANNER_URL is not set. Copy .env.example to .env.local.");
  });

  it("treats an empty variable as missing", () => {
    vi.stubEnv("REGISTRY_URL", "");
    expect(() => getConfig()).toThrow("REGISTRY_URL is not set. Copy .env.example to .env.local.");
  });
});
