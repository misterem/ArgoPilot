// Shapes of the services' JSON, exactly as they send it.

export type Farm = { id: string; name: string };

export type Plot = {
  id: string;
  farm_id: string;
  name: string;
  area_m2: number;
  crop_id: string;
  planting_date: string;
  soil_id: string;
  row_spacing_m: number;
  emitter_spacing_m: number;
  emitter_id: string;
  lat: number;
  lon: number;
};

export type Crop = { id: string; name: string };

export type PlanDay = {
  date: string;
  et0_mm: number;
  rain_mm: number;
  kc: number;
  etc_mm: number;
  irrigation_mm: number;
  litres: number;
  run_minutes: number;
  bucket_end_mm: number;
  stale: boolean;
};

export type Plan = {
  plot_id: string;
  crop_id: string;
  planting_date: string;
  season_end: string;
  bucket_capacity_mm: number;
  threshold_mm: number;
  fetched_at: string;
  stale: boolean;
  days: PlanDay[];
};

export type FetchError =
  | { kind: "not_found" }
  | { kind: "unavailable" }
  | { kind: "problem"; status: number; code: string; detail: string };

export type Result<T> = { ok: true; data: T } | { ok: false; error: FetchError };
