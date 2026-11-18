"use client"; // error boundaries must be client components

import { ErrorPanel } from "@/components/error-panel";

/** Anything unexpected inside a page: say so plainly, never a stack trace (FR-2.18). */
export default function Error({ retry }: { error: unknown; retry: () => void }) {
  return (
    <>
      <ErrorPanel
        title="Something went wrong on this page"
        text="A service sent an answer this page couldn't read. Try again in a minute."
      />
      <button
        type="button"
        onClick={() => retry()}
        className="mt-3 rounded-md bg-ink px-4 py-2 text-sm font-bold text-surface"
      >
        Try again
      </button>
    </>
  );
}
