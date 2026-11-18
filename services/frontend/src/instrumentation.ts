// Runs once when the Next.js server starts (next dev / next start, not next build):
// a missing service URL stops startup with a clear message instead of failing on the first request.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { getConfig } = await import("./lib/config");
    getConfig();
  }
}
