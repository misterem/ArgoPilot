import { getConfig } from "./config";
import { fetchJson, segment } from "./fetch-json";
import type { Plan, Result } from "./types";

// Longer than the planner's own worst case (~20 s waiting on weather-service during an outage).
const TIMEOUT_MS = 25000;

export function getPlan(plotId: string, days = 7): Promise<Result<Plan>> {
  return fetchJson<Plan>(`${getConfig().plannerUrl}/v1/plots/${segment(plotId)}/plan?days=${days}`, TIMEOUT_MS);
}
