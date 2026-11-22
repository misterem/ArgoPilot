export default function Loading() {
  return (
    <section aria-busy className="mt-12 flex gap-4 rounded-md bg-surface p-4">
      <div className="min-h-[150px] w-11 shrink-0 rounded-[4px] border-2 border-ink/20" />
      <p className="self-center text-[15px] text-muted">Working out today&apos;s plan…</p>
    </section>
  );
}
