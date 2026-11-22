# frontend

The AgroPilot web app, for a grower with a phone in the field: the farms and their plots, and for each plot **today's irrigation answer** ("Water for 1 h 54 min" or "No irrigation today"), a soil-water gauge, and the next 7 days as bars you can tap for that day's numbers.

Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui. Port 3000.

## Run

Needs registry-service (8000), weather-service (8001) and planner-service (8002) running.

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

| Script | |
|---|---|
| `npm run dev` | development server |
| `npm run build` / `npm start` | production build and server |
| `npm run lint` | ESLint |
| `npm test` | Vitest unit tests for the copy and plan helpers (`src/lib/*.test.ts`) |

## Configuration

`.env.local` (copy `.env.example`):

| Variable | Example |
|---|---|
| `REGISTRY_URL` | `http://127.0.0.1:8000` |
| `WEATHER_URL` | `http://127.0.0.1:8001` |
| `PLANNER_URL` | `http://127.0.0.1:8002` |

All three are required: `npm run dev` / `npm start` stop at startup with "`<NAME>` is not set. Copy .env.example to .env.local." `npm run build` doesn't need them.

Only the Next.js server calls the services (from `src/lib/`); the browser never does. Every call is uncached, with a timeout: registry 5 s, planner 25 s (longer than the planner's own worst case of ~20 s while Open-Meteo is down), status checks 2 s.

## Pages

- **`/`**: every farm with its plots; each plot links to its page.
- **`/plots/{id}`**: today's answer first, with a gauge of the soil water left at the end of today against the refill line (dashed). Then the week as bars sized by run time (hours:minutes), forecast rain under its day; tap a bar to see that day's run time, litres, crop use (Kc × ET0), rain and soil water.
- A status line on every page shows whether registry, weather and planner answer `GET /health`.

## When something is wrong

- **Stale forecast** (Open-Meteo down, weather-service answering from its cache): the numbers stay, a yellow note right under them says how old the forecast is, and the affected bars are striped.
- **Planner errors** are shown in place of the plan, with what happened and what to do: "Weather service is not answering", "Registry service is not answering", "Planner service is not answering", or "No plan: the season ended" with the planner's explanation.
- **Unknown plot**: "No plot with this id."

## Seeing a plan with the demo data

The demo plots in `registry-service/demo.sql` were planted in February to May 2026, so their seasons are over and their pages say "No plan: the season ended". To see a full plan, create a plot (or PATCH one) with a planting date in the last few months through the registry API, for example a tomato plot planted 99 days ago is in mid-season.

## Layout

- `src/app/`: `page.tsx` (farms), `plots/[id]/page.tsx` (plot), `loading.tsx`, `not-found.tsx`, `layout.tsx` (header and status line)
- `src/components/`: `hero.tsx`, `gauge.tsx`, `week-bars.tsx` (the only client component: switches the selected day, no fetching), `stale-note.tsx`, `error-panel.tsx`, `status-line.tsx`
- `src/lib/`: `config.ts`, `registry.ts`, `planner.ts`, `health.ts`, `fetch-json.ts` (no-store fetch, timeouts, failures as values), `format.ts` and `plan.ts` (how numbers, dates and errors read), `types.ts`
- Design tokens (colours, font) in `src/app/globals.css`; Next.js 16 with Cache Components, so request-time data sits under `loading.tsx` / `<Suspense>` and components call `connection()`.
