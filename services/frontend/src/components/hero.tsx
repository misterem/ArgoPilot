import { Gauge } from "@/components/gauge";
import { formatDayShort, formatDuration } from "@/lib/format";
import { heroSubline } from "@/lib/plan";
import type { Plan } from "@/lib/types";

/** Today's recommendation, first and biggest (FR-2.16). */
export function Hero({ plan }: { plan: Plan }) {
  const today = plan.days[0];
  const answer = today.run_minutes > 0 ? `Water for ${formatDuration(today.run_minutes)}` : "No irrigation today";
  return (
    <section aria-label="Today's recommendation" className="mt-3 flex gap-4 rounded-md bg-surface p-4">
      <Gauge plan={plan} />
      <div className="min-w-0">
        <p className="text-[15px] text-muted">Today, {formatDayShort(today.date)}</p>
        <p id="answer" className="mt-1 mb-2 text-[40px] leading-[1.02] font-extrabold tracking-[-0.01em] text-balance">
          {answer}
        </p>
        <p className="text-sm leading-snug text-muted">{heroSubline(today)}</p>
      </div>
    </section>
  );
}
