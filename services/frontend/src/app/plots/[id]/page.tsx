import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";

import { ErrorPanel } from "@/components/error-panel";
import { Hero } from "@/components/hero";
import { StaleNote } from "@/components/stale-note";
import { WeekBars } from "@/components/week-bars";
import { describePlanError, seasonEndNote } from "@/lib/plan";
import { getPlan } from "@/lib/planner";
import { getCrop, getFarm, getPlot } from "@/lib/registry";

export default async function PlotPage({ params }: PageProps<"/plots/[id]">) {
  await connection();
  const { id } = await params;
  const [plot, plan] = await Promise.all([getPlot(id), getPlan(id)]);

  const back = (
    <Link href="/" className="mt-4 inline-block text-sm text-water underline-offset-2 hover:underline">
      All farms
    </Link>
  );

  if (!plot.ok) {
    if (plot.error.kind === "not_found") notFound();
    return (
      <>
        {back}
        <ErrorPanel title="Registry service is not answering" text="The plot's details can't be read. Try again in a minute." />
      </>
    );
  }

  const [farm, crop] = await Promise.all([getFarm(plot.data.farm_id), getCrop(plot.data.crop_id)]);
  const heading = (
    <>
      {back}
      <p className="mt-1 text-sm text-muted">{farm.ok ? farm.data.name : plot.data.farm_id}</p>
      <h1 className="text-[22px] leading-tight font-bold">
        {plot.data.name}, {(crop.ok ? crop.data.name : plot.data.crop_id).toLowerCase()}
      </h1>
    </>
  );

  if (!plan.ok) {
    const described = describePlanError(plan.error);
    if (described === "not_found") notFound();
    return (
      <>
        {heading}
        <ErrorPanel title={described.title} text={described.text} />
      </>
    );
  }

  return (
    <>
      {heading}
      <Hero plan={plan.data} />
      {plan.data.stale && <StaleNote fetchedAt={plan.data.fetched_at} />}
      <WeekBars days={plan.data.days} capacityMm={plan.data.bucket_capacity_mm} seasonNote={seasonEndNote(plan.data)} />
    </>
  );
}
