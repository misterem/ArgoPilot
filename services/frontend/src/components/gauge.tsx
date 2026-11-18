import { gauge } from "@/lib/plan";
import type { Plan } from "@/lib/types";

/** The soil "bucket": water left at the end of today against the refill line (dashed). */
export function Gauge({ plan }: { plan: Plan }) {
  const { water, refill } = gauge(plan);
  const label =
    `Soil water at end of today: ${Math.round(plan.days[0].bucket_end_mm)} of ` +
    `${Math.round(plan.bucket_capacity_mm)} mm; refill line at ${Math.round(plan.threshold_mm)} mm.`;
  return (
    <div role="img" aria-label={label} className="relative w-11 shrink-0 self-stretch min-h-[150px] overflow-visible">
      <div className="absolute inset-0 overflow-hidden rounded-[4px] border-2 border-ink bg-soil">
        <div className="absolute inset-x-0 top-0 bg-surface" style={{ height: `${(1 - water) * 100}%` }} />
        <div className="absolute inset-x-0 bottom-0 bg-water/85" style={{ height: `${water * 100}%` }} />
      </div>
      <div
        aria-hidden
        className="absolute -inset-x-2 border-t-2 border-dashed border-refill"
        style={{ top: `${(1 - refill) * 100}%` }}
      />
    </div>
  );
}
