import { formatDayShort, formatLitres } from "./format";
import type { FetchError, Plan, PlanDay } from "./types";

export type ErrorText = { title: string; text: string };

const PLANNER_DOWN: ErrorText = { title: "Planner service is not answering", text: "Try again in a minute." };

/** What the plot page says when the planner doesn't return a plan (FR-2.18). */
export function describePlanError(error: FetchError): ErrorText | "not_found" {
  if (error.kind === "not_found") return "not_found";
  if (error.kind === "unavailable") return PLANNER_DOWN;
  if (error.status === 422) {
    return error.detail.startsWith("Season ended")
      ? { title: "No plan: the season ended", text: error.detail }
      : { title: "No plan for this plot", text: error.detail };
  }
  if (error.code === "UPSTREAM_UNAVAILABLE" && error.detail.startsWith("weather-service")) {
    return { title: "Weather service is not answering", text: "The plan needs the forecast. Try again in a minute." };
  }
  if (error.code === "UPSTREAM_UNAVAILABLE" && error.detail.startsWith("registry-service")) {
    return { title: "Registry service is not answering", text: "The plan needs the plot's details. Try again in a minute." };
  }
  return PLANNER_DOWN;
}

const clamp = (x: number) => Math.min(1, Math.max(0, x));

/** Today's soil water and the refill line, as fractions of the full bucket. */
export function gauge(plan: Pick<Plan, "bucket_capacity_mm" | "threshold_mm" | "days">) {
  const capacity = plan.bucket_capacity_mm;
  return {
    water: clamp(plan.days[0].bucket_end_mm / capacity),
    refill: clamp(plan.threshold_mm / capacity),
  };
}

/** Bar heights 0..1, the longest run = 1. A week with no irrigation is all 0. */
export function barHeights(minutes: number[]): number[] {
  const max = Math.max(0, ...minutes);
  return minutes.map((m) => (max === 0 ? 0 : m / max));
}

export function heroSubline(day: Pick<PlanDay, "run_minutes" | "litres" | "rain_mm">): string {
  if (day.run_minutes > 0) return `${formatLitres(day.litres)} litres through the drip line.`;
  return day.rain_mm > 0 ? "Rain and stored soil water cover today's use." : "Stored soil water covers today's use.";
}

/** Shown when the season ends inside the window and the plan has fewer days. */
export function seasonEndNote(plan: Pick<Plan, "season_end" | "days">, requestedDays = 7): string | null {
  if (plan.days.length >= requestedDays) return null;
  return `The season ends on ${formatDayShort(plan.season_end)}; the plan stops there.`;
}
