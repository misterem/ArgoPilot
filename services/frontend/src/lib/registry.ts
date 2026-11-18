import { getConfig } from "./config";
import { fetchJson, isUsableId, NOT_FOUND, segment } from "./fetch-json";
import type { Crop, Farm, Plot, Result } from "./types";

const TIMEOUT_MS = 5000;

const isList = (body: unknown) => Array.isArray(body);
const isOne = (body: unknown) =>
  typeof body === "object" && body !== null && !Array.isArray(body) && typeof (body as { id?: unknown }).id === "string";

function list<T>(path: string): Promise<Result<T[]>> {
  return fetchJson<T[]>(`${getConfig().registryUrl}${path}`, TIMEOUT_MS, isList);
}

function one<T>(path: string, id: string): Promise<Result<T>> {
  if (!isUsableId(id)) return Promise.resolve(NOT_FOUND);
  return fetchJson<T>(`${getConfig().registryUrl}${path}/${segment(id)}`, TIMEOUT_MS, isOne);
}

export const getFarms = () => list<Farm>("/v1/farms");
export const getPlots = () => list<Plot>("/v1/plots");
export const getCrops = () => list<Crop>("/v1/crops");
export const getFarm = (id: string) => one<Farm>("/v1/farms", id);
export const getPlot = (id: string) => one<Plot>("/v1/plots", id);
export const getCrop = (id: string) => one<Crop>("/v1/crops", id);
