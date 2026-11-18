// Base URLs of the three services, read from the server environment (.env.local).
// Only server code imports this module: the browser never calls the services.

export type Config = { registryUrl: string; weatherUrl: string; plannerUrl: string };

type Name = "REGISTRY_URL" | "WEATHER_URL" | "PLANNER_URL";

function required(name: Name): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is not set. Copy .env.example to .env.local.`);
  }
  return value.replace(/\/+$/, "");
}

export function getConfig(): Config {
  return {
    registryUrl: required("REGISTRY_URL"),
    weatherUrl: required("WEATHER_URL"),
    plannerUrl: required("PLANNER_URL"),
  };
}
