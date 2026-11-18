import { connection } from "next/server";

import { checkHealth } from "@/lib/health";

const SERVICES = [
  ["registry", "Registry"],
  ["weather", "Weather"],
  ["planner", "Planner"],
] as const;

function Dot({ label, up }: { label: string; up: boolean | null }) {
  const state = up === null ? "checking" : up ? "up" : "not answering";
  const colour = up === null ? "bg-muted/40" : up ? "bg-up" : "bg-down";
  return (
    <li className="flex items-center gap-1.5" aria-label={`${label}: ${state}`}>
      <span aria-hidden className={`inline-block size-2 rounded-full ${colour}`} />
      <span className={up === false ? "font-bold text-down" : undefined}>{label}</span>
    </li>
  );
}

export function StatusLineFallback() {
  return (
    <ul className="flex gap-3 text-xs text-muted" aria-label="Service status: checking">
      {SERVICES.map(([key, label]) => (
        <Dot key={key} label={label} up={null} />
      ))}
    </ul>
  );
}

export async function StatusLine() {
  await connection(); // request time only: never prerendered, never cached
  const health = await checkHealth();
  return (
    <ul className="flex gap-3 text-xs text-muted" aria-label="Service status">
      {SERVICES.map(([key, label]) => (
        <Dot key={key} label={label} up={health[key]} />
      ))}
    </ul>
  );
}
