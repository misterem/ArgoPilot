import { formatAge } from "@/lib/format";

/** Right under the numbers it affects (FR-2.17). */
export function StaleNote({ fetchedAt }: { fetchedAt: string }) {
  return (
    <p role="status" className="mt-2 rounded-md border-l-4 border-refill bg-refill-bg px-3 py-2 text-[13px] leading-snug text-[#5a4500]">
      Based on an old forecast from {formatAge(fetchedAt, new Date())} ago: the weather provider isn&apos;t answering. These
      numbers may be off.
    </p>
  );
}
