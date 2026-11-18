import { getConfig } from "./config";
import { fetchJson, segment } from "./fetch-json";
import type { Crop, Farm, Plot, Result } from "./types";

const TIMEOUT_MS = 5000;

function get<T>(path: string): Promise<Result<T>> {
  return fetchJson<T>(`${getConfig().registryUrl}${path}`, TIMEOUT_MS);
}

export const getFarms = () => get<Farm[]>("/v1/farms");
export const getPlots = () => get<Plot[]>("/v1/plots");
export const getCrops = () => get<Crop[]>("/v1/crops");
export const getFarm = (id: string) => get<Farm>(`/v1/farms/${segment(id)}`);
export const getPlot = (id: string) => get<Plot>(`/v1/plots/${segment(id)}`);
export const getCrop = (id: string) => get<Crop>(`/v1/crops/${segment(id)}`);
