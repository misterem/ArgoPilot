import { getConfig } from "./config";
import { fetchJson, isUsableId, NOT_FOUND, segment } from "./fetch-json";
import type { Plan, Result } from "./types";

// Longer than the planner's own worst case (~20 s waiting on weather-service during an outage).
const TIMEOUT_MS = 25000;

// The page indexes days[0]: a plan without days is a broken planner, not an empty plan.
const hasDays = (body: unknown) => {
  const days = (body as { days?: unknown } | null)?.days;
  return Array.isArray(days) && days.length > 0;
};

export function getPlan(plotId: string, days = 7): Promise<Result<Plan>> {
  if (!isUsableId(plotId)) return Promise.resolve(NOT_FOUND);
  return fetchJson<Plan>(`${getConfig().plannerUrl}/v1/plots/${segment(plotId)}/plan?days=${days}`, TIMEOUT_MS, hasDays);
}
