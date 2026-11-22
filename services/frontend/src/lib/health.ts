import { getConfig } from "./config";

export type Health = { registry: boolean; weather: boolean; planner: boolean };

const TIMEOUT_MS = 2000;

async function isUp(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${baseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return response.status === 200;
  } catch {
    return false;
  }
}

export async function checkHealth(): Promise<Health> {
  const { registryUrl, weatherUrl, plannerUrl } = getConfig();
  const [registry, weather, planner] = await Promise.all([isUp(registryUrl), isUp(weatherUrl), isUp(plannerUrl)]);
  return { registry, weather, planner };
}
