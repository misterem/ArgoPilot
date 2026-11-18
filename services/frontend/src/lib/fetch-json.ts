import type { FetchError, Result } from "./types";

const UNAVAILABLE: FetchError = { kind: "unavailable" };

/** One path segment: "/" and "?" are encoded, so an id can't reach another route. */
export function segment(id: string): string {
  return encodeURIComponent(id);
}

/** "", "." and ".." can't be ids: URL parsing collapses them (even as %2E) and the request would reach another route. */
export function isUsableId(id: string): boolean {
  return id !== "" && id !== "." && id !== "..";
}

export const NOT_FOUND: Result<never> = { ok: false, error: { kind: "not_found" } };

/**
 * GET a service's JSON. Never throws: every failure comes back as a FetchError.
 * `looksRight` guards the parts pages rely on; a 200 that fails it is treated as the service being broken.
 */
export async function fetchJson<T>(
  url: string,
  timeoutMs: number,
  looksRight: (body: unknown) => boolean = () => true,
): Promise<Result<T>> {
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
  if (response.ok) return looksRight(body) ? { ok: true, data: body as T } : { ok: false, error: UNAVAILABLE };

  const problem = body as { code?: unknown; detail?: unknown };
  if (typeof problem?.code === "string" && typeof problem?.detail === "string") {
    return { ok: false, error: { kind: "problem", status: response.status, code: problem.code, detail: problem.detail } };
  }
  return { ok: false, error: UNAVAILABLE };
}
