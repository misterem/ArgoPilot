import type { FetchError, Result } from "./types";

const UNAVAILABLE: FetchError = { kind: "unavailable" };

/** One path segment: "/", "?" and dots are encoded, so an id can never reach another route. */
export function segment(id: string): string {
  return encodeURIComponent(id).replace(/\./g, "%2E");
}

/** GET a service's JSON. Never throws: every failure comes back as a FetchError. */
export async function fetchJson<T>(url: string, timeoutMs: number): Promise<Result<T>> {
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(timeoutMs) });
  } catch {
    return { ok: false, error: UNAVAILABLE }; // refused, DNS, timeout
  }
  if (response.status === 404) return { ok: false, error: { kind: "not_found" } };

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, error: UNAVAILABLE };
  }
  if (response.ok) return { ok: true, data: body as T };

  const problem = body as { code?: unknown; detail?: unknown };
  if (typeof problem?.code === "string" && typeof problem?.detail === "string") {
    return { ok: false, error: { kind: "problem", status: response.status, code: problem.code, detail: problem.detail } };
  }
  return { ok: false, error: UNAVAILABLE };
}
