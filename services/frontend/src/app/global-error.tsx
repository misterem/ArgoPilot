"use client"; // replaces the root layout when it fails, so it brings its own document and plain styles

export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#eef3f5", color: "#18211f", fontFamily: "system-ui, sans-serif" }}>
        <title>AgroPilot</title>
        <main style={{ maxWidth: 480, margin: "0 auto", padding: "24px 16px" }}>
          <div role="alert" style={{ background: "#fff", borderLeft: "6px solid #c0392b", borderRadius: 6, padding: 16 }}>
            <p style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Something went wrong</p>
            <p style={{ margin: "6px 0 0" }}>AgroPilot couldn&apos;t load this page. Try again in a minute.</p>
          </div>
          <button
            type="button"
            onClick={() => retry()}
            style={{ marginTop: 12, background: "#18211f", color: "#fff", border: 0, borderRadius: 6, padding: "8px 16px", fontWeight: 700 }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
