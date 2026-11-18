"use client";

import { useState } from "react";

import { formatClock, formatDayLong, formatDuration, formatLitres, formatMm, formatWeekday } from "@/lib/format";
import { barHeights } from "@/lib/plan";
import type { PlanDay } from "@/lib/types";

const KC = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 });

type Props = { days: PlanDay[]; capacityMm: number; seasonNote: string | null };

/** The week as bars sized by run time; tap a bar for that day's numbers. Gets its data as props: no fetching here. */
export function WeekBars({ days, capacityMm, seasonNote }: Props) {
  const [selected, setSelected] = useState(0);
  const heights = barHeights(days.map((d) => d.run_minutes));
  const anyStale = days.some((d) => d.stale);
  const day = days[selected];

  return (
    <section aria-labelledby="week-heading" className="mt-6">
      <h2 id="week-heading" className="text-[15px] font-bold">
        Next {days.length} {days.length === 1 ? "day" : "days"}
      </h2>

      <div className="mt-2 grid grid-cols-7 gap-1.5">
        {days.map((d, i) => {
          const label =
            d.run_minutes > 0
              ? `${formatDayLong(d.date)}, water ${formatDuration(d.run_minutes)}`
              : `${formatDayLong(d.date)}, no irrigation`;
          const colour = d.stale
            ? "bg-[repeating-linear-gradient(135deg,var(--color-water)_0_6px,#6fa3d1_6px_12px)]"
            : i === 0
              ? "bg-ink"
              : "bg-water";
          return (
            <button
              key={d.date}
              type="button"
              aria-pressed={i === selected}
              aria-label={label}
              onClick={() => setSelected(i)}
              className={`flex h-[170px] flex-col items-center justify-end rounded-sm px-0.5 pt-1 ${
                i === selected ? "bg-surface outline-2 outline-ink" : ""
              }`}
            >
              <span className="tabular mb-1 text-xs">{d.run_minutes > 0 ? formatClock(d.run_minutes) : "none"}</span>
              {d.run_minutes > 0 ? (
                <span
                  aria-hidden
                  className={`block w-full rounded-t-[3px] ${colour}`}
                  style={{ height: `${Math.max(heights[i] * 130, 4)}px` }}
                />
              ) : (
                <span aria-hidden className="block w-full border-t-2 border-[#9aa6a4]" />
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-1 grid grid-cols-7 gap-1.5 border-t border-[#9aa6a4] pt-1.5" aria-hidden>
        {days.map((d, i) => (
          <div key={d.date} className="text-center text-xs text-muted">
            <span className={i === 0 ? "font-bold text-ink" : undefined}>{i === 0 ? "Today" : formatWeekday(d.date)}</span>
            <span className="block min-h-4 text-[11px] text-water">{d.rain_mm >= 0.1 ? `${formatMm(d.rain_mm)} mm` : ""}</span>
          </div>
        ))}
      </div>

      <dl aria-live="polite" className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-md bg-surface p-4 text-sm">
        <dt className="col-span-2 mb-1 text-[15px] font-bold">{formatDayLong(day.date)}</dt>
        <dt className="text-muted">Run time</dt>
        <dd className="tabular">{day.run_minutes > 0 ? formatDuration(day.run_minutes) : "No irrigation"}</dd>
        <dt className="text-muted">Water</dt>
        <dd className="tabular">
          {formatLitres(day.litres)} litres ({formatMm(day.irrigation_mm)} mm)
        </dd>
        <dt className="text-muted">Crop use</dt>
        <dd className="tabular">
          {formatMm(day.etc_mm)} mm (Kc {KC.format(day.kc)} × ET0 {formatMm(day.et0_mm)} mm)
        </dd>
        <dt className="text-muted">Rain</dt>
        <dd className="tabular">{formatMm(day.rain_mm)} mm</dd>
        <dt className="text-muted">Soil water</dt>
        <dd className="tabular">
          {formatMm(day.bucket_end_mm)} of {formatMm(capacityMm)} mm at end of day
        </dd>
        {day.stale && (
          <dd className="col-span-2 mt-1 font-bold text-[#5a4500]">Old forecast: these numbers may be off.</dd>
        )}
      </dl>

      {seasonNote && <p className="mt-3 text-sm">{seasonNote}</p>}
      <p className="mt-2 text-xs leading-snug text-muted">
        Run time in hours:minutes. Blue under a day is forecast rain.{anyStale ? " Striped: old forecast." : ""}
      </p>
    </section>
  );
}
