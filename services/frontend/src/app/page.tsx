import Link from "next/link";
import { connection } from "next/server";

import { ErrorPanel } from "@/components/error-panel";
import { formatLitres } from "@/lib/format";
import { getCrops, getFarms, getPlots } from "@/lib/registry";

export default async function FarmsPage() {
  await connection();
  const [farms, plots, crops] = await Promise.all([getFarms(), getPlots(), getCrops()]);

  if (!farms.ok || !plots.ok || !crops.ok) {
    return (
      <>
        <h1 className="mt-4 text-[26px] font-bold">Farms</h1>
        <ErrorPanel title="Registry service is not answering" text="Farms can't be listed. Try again in a minute." />
      </>
    );
  }

  const cropName = new Map(crops.data.map((c) => [c.id, c.name]));

  return (
    <>
      <h1 className="mt-4 text-[26px] font-bold">Farms</h1>
      {farms.data.length === 0 && <p className="mt-4 text-muted">No farms yet.</p>}
      {farms.data.map((farm) => {
        const farmPlots = plots.data.filter((p) => p.farm_id === farm.id);
        return (
          <section key={farm.id} className="mt-6" aria-labelledby={`farm-${farm.id}`}>
            <h2 id={`farm-${farm.id}`} className="text-lg font-bold">
              {farm.name}
            </h2>
            {farmPlots.length === 0 ? (
              <p className="mt-2 text-sm text-muted">No plots yet</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {farmPlots.map((plot) => (
                  <li key={plot.id}>
                    <Link
                      href={`/plots/${encodeURIComponent(plot.id)}`}
                      className="flex items-baseline justify-between gap-3 rounded-md bg-surface px-4 py-3 text-base hover:bg-white/70"
                    >
                      <span className="min-w-0 font-bold">{plot.name}</span>
                      <span className="shrink-0 text-right text-sm text-muted">
                        {cropName.get(plot.crop_id) ?? plot.crop_id}, {formatLitres(plot.area_m2)} m²
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </>
  );
}
