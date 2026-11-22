# frontend — design

Part 4 of P2 (the P2 task brief, `tasks/p2.md` in the course repo: "The `frontend`"). New app in `services/frontend`, port 3000.

## Intent

A grower won't use `curl`. They stand in the field with a phone, often in bright sun, and want one answer: water this plot today, and for how long. The frontend lists the farms and plots and, for a plot, puts today's answer first, big and clear, then the week. It must stay honest when something upstream is wrong: a stale forecast is labelled next to the numbers it affects, and an outage says which service is down, never a blank page or a stack trace.

## Goals (spec)

- **FR-2.15** `/` lists every farm with its plots; each plot links to `/plots/{id}`.
- **FR-2.16** The plot page shows today's recommendation first, big and clear ("Water for 38 minutes" / "No irrigation today"), then the 7-day plan as a table or timeline.
- **FR-2.17** When the forecast is stale, the user sees it next to the numbers it affects.
- **FR-2.18** When the planner answers with an error, the user sees what happened (e.g. which service is down), not a blank page or a stack trace.
- **FR-2.19** A small status line shows whether each of the three services is up (`GET /health`).
- **NFR-2.8** At 375 px: no horizontal scrolling, and today's recommendation is visible without scrolling.
- Brief's build rules: Next.js (App Router, TypeScript, Tailwind CSS, shadcn/ui), frontend-design skill; read the APIs first; the browser never calls the services; pages fetch on the server; all service calls in `src/lib/`, using `REGISTRY_URL`, `WEATHER_URL`, `PLANNER_URL` from `.env.local`; `.env.example` committed; no other pages or features; `npm run build` and `npm run lint` pass; commit `services/frontend` without `node_modules/`, `.next/`, `.env.local`.

## Non-goals

- No editing (no forms, no PATCH of planting dates), no login, no other pages.
- No recommendation on the farms list *(user: keep it plain; it would cost one planner call per plot)*.
- No dark theme (bright-sun reading is the case that matters). No charting library.
- No change to the services or to `demo.sql`: the demo plots are past their season, so their pages show the "season ended" message. A plot with a recent planting date (created through the registry API) shows a full plan.

## Anti-goals

- A plan screen that looks normal while the forecast is stale.
- "No irrigation" shown for anything other than a day the planner returned `run_minutes: 0`.
- A blank page, a spinner that never ends, or a raw error/stack trace.
- Any request from the browser to registry, weather or planner.

## Approaches considered

- **A. Server components fetch everything; the week bars are plain HTML/CSS buttons in one small client component (`WeekBars`) that only switches which day's details are shown.** *(Chosen by the user.)* No browser→service calls, accessible bars, light page, full control of the dashed refill line, striped stale bars and rain marks.
- B. shadcn Chart (Recharts): standard, but a large library for 7 bars, hover tooltips are awkward on phones, harder to style.
- C. Server-only, each bar a `?day=` link: no client JS, but every tap re-runs the planner (slow in the field, up to ~20 s during a weather outage).

## Look *(user, from mockups: A's "today" gauge, fonts and colours; B's weekly bars; tap a bar for that day's details)*

The mockups are in `.superpowers/brainstorm/` (`plot-page-v2.html` is the chosen one).

**Tokens**

| Name | Hex | Use |
|---|---|---|
| sky | `#EEF3F5` | page background |
| surface | `#FFFFFF` | hero, plot rows, detail panel |
| ink | `#18211F` | text, today's bar, gauge frame |
| muted | `#4A5755` | secondary text |
| water | `#1F6FB2` | water in the gauge, bars, rain marks, links |
| soil | `#7A5230` | dry soil in the gauge |
| refill | `#E0A100` | dashed refill line; stale notes (on `#FFF4D6`) |
| up / down | `#2E8B57` / `#C0392B` | status dots; error edge |

**Type:** one family, Atkinson Hyperlegible Next (designed for legibility), via `next/font/google`; if that family isn't available in `next/font`, Atkinson Hyperlegible. Scale: answer 44 px / 800, plot name 22 px / 700, section 15 px / 700, body 14–16 px, small 12 px; tabular figures for numbers. Sentence case everywhere; no all-caps labels.

**Layout:** single column, left-aligned, 16–18 px gutters, max width ~480 px centred on wider screens. White surfaces with a 6 px radius only where content is grouped (hero, plot rows, detail panel); no shadows. Motion: none on load; the detail panel swap is instant (reduced motion respected anyway). Visible keyboard focus.

## Pages

### Every page

- **Status line** (top, small): `● Registry ● Weather ● Planner`, green dot = `/health` answered 200 within 2 s, red = anything else (`/health` only, per FR-2.19: a stale forecast means Open-Meteo is down, not weather-service, so the Weather dot stays green and the stale note carries that; the red dot on the mockup's stale screen was a mockup error) *(agent)*; each dot has a text label so colour isn't the only signal ("Weather: not answering"). Checked server-side in parallel on every request; never delays the page more than 2 s.
- Small "AgroPilot" name in the header *(agent)*.

### `/` — Farms

- Heading "Farms". For each farm (registry order), its name, then its plots as rows: plot name, crop name and area (`Tomato, 1,000 m²`), the whole row a link to `/plots/{id}`. A farm with no plots says "No plots yet". No farms: "No farms yet."
- Data: `GET /v1/farms`, `GET /v1/plots`, `GET /v1/crops` (crop names) in parallel.
- Registry down: an error panel "Registry service is not answering, so farms can't be listed. Try again in a minute." (status line shows it red too).

### `/plots/[id]` — Plot

Order (top to bottom): status line, "All farms" link, farm name, "{plot name}, {crop name}", then the **hero**, then **Next 7 days**.

- **Hero** (white panel): the gauge on the left, on the right "Today, Wed 18 Nov", the answer, and one sub-line.
  - Answer: `run_minutes > 0` → "Water for {duration}"; `run_minutes == 0` → "No irrigation today". Duration: under 60 → "38 minutes" (1 → "1 minute"); 60+ → "1 h 53 min" (exact hours → "2 h").
  - Sub-line: "{litres, thousands separator} litres through the drip line." or, when no irrigation, "Rain and stored soil water cover today's use." if today's `rain_mm` > 0, else "Stored soil water covers today's use."
  - **Gauge**: a vertical bucket. Height = `bucket_capacity_mm`; water fill = today's `bucket_end_mm` / capacity; dashed refill line at `threshold_mm` / capacity; soil colour behind. Text alternative: "Soil water at end of today: 73 of 123 mm; refill line at 73 mm."
- **Stale** (`stale: true`): directly under the hero's numbers a note "Based on an old forecast from {age} ago: the weather provider isn't answering. These numbers may be off." (age from `fetched_at`, e.g. "11 h"); every stale bar striped; the detail panel repeats "Old forecast" for that day.
- **Next 7 days**: one bar per plan day (fewer if the season ends: note "The season ends on {date}; the plan stops there.").
  - Bar height ∝ `run_minutes` against the week's largest; `run_minutes == 0` → a flat line labelled "none". Label above each bar: `h:mm`. Below: weekday ("Today" for the first), and the forecast rain under its day when `rain_mm` ≥ 0.1 ("9 mm"). Today's bar in ink, others water-blue.
  - Each bar is a `<button>` (`aria-pressed`, label like "Thursday 19 November, water 2 h 03 min"); tapping selects it. Today is selected at first.
  - **Day details panel** under the bars, for the selected day: date; run time; litres; water (irrigation_mm); crop use (etc_mm) = Kc × ET0 shown as "Kc 1.15 × ET0 2.98 mm"; rain; soil water at end of day (bucket_end_mm of capacity). Stale → "Old forecast" line.
  - Legend line: "Run time in hours:minutes. Blue under a day is forecast rain." (+ "Striped: old forecast." when stale).
- Data: `GET /v1/plots/{id}` and the planner plan in parallel, then `GET /v1/farms/{farm_id}` and `GET /v1/crops/{crop_id}`. Registry says 404 → Next's not-found page "No plot with this id." with a link to all farms.
- **Planner errors** (FR-2.18), shown in place of hero and bars, as a white panel with a red edge, title + sentence:

| Planner answer | Title | Text |
|---|---|---|
| 422, detail starts "Season ended" | No plan: the season ended | the planner's detail as it comes (it already says to update the planting date; no parsing of its text) *(agent)* |
| 422 other (crop without parameters, season not started) | No plan for this plot | the planner's detail |
| 503 `UPSTREAM_UNAVAILABLE`, detail starts "weather-service" | Weather service is not answering | "The plan needs the forecast. Try again in a minute." |
| 503, detail starts "registry-service" | Registry service is not answering | "The plan needs the plot's details. Try again in a minute." |
| planner unreachable / timeout / 5xx / non-JSON | Planner service is not answering | "Try again in a minute." |
| 404 | (not-found page) | |

  If the plot itself can't be read from the registry (down), the page shows the registry panel without plot details.
- **Loading**: `loading.tsx` shows the status line area and a skeleton hero ("Working out today's plan…") while the server waits.

## Data layer (`src/lib/`) *(agent)*

- `config.ts`: reads `REGISTRY_URL`, `WEATHER_URL`, `PLANNER_URL`; a missing one throws "`<NAME>` is not set. Copy .env.example to .env.local." `instrumentation.ts` calls it at server start, so `next dev` / `next start` fail fast; `next build` doesn't need the variables.
- `registry.ts`, `planner.ts`, `health.ts`: typed fetchers, `cache: "no-store"`, timeouts via `AbortSignal.timeout`: registry 5 s, planner 25 s (above the planner's ~20 s worst case), health 2 s. They return a result type (`{ ok: true, data } | { ok: false, error }`) rather than throwing, so pages render each failure deliberately.
- `format.ts`: duration, litres, dates (plan dates are plain local dates, formatted without time-zone conversion, `en-GB`: "Wed 18 Nov"), forecast age.
- `plan.ts`: maps a planner error to the table above; gauge fractions.
- Types mirror the services' JSON exactly (no extra fields invented).
- Small unit tests (Vitest) for `format.ts` and `plan.ts` (duration edge cases, error mapping, gauge fractions); `npm test` *(agent: not a feature, keeps the copy rules honest)*.

## Verification

- `npm run build`, `npm run lint`, `npm test` pass.
- With the three services running on a throwaway registry DB that also has one plot with a recent planting date: `/` lists farms and plots; that plot shows a real plan; a demo plot shows "season ended"; stopping weather shows the weather error; a fake stale case is covered by unit tests (and, if practical, by stopping Open-Meteo access is not needed).
- NFR-2.8 in the browser pane at 375 × 812: no horizontal scroll (`document.documentElement.scrollWidth <= 375`) on both pages; the hero's answer is inside the first viewport.
- `git status`: `node_modules/`, `.next/`, `.env.local` not tracked.

## Constraints

- Node 25 locally (`create-next-app@latest`, current Next.js, React, Tailwind, shadcn CLI); exact versions pinned by `package-lock.json`.
- The browser never calls a service; only server code under `src/lib/` does.

## Settled by the agent (builder check)

- Durations pad minutes in the hours form ("1 h 05 min"), matching the bar labels' `h:mm`.
- If the plot loads but the farm or crop lookup fails, the page still shows the plan, with the raw `farm_id` / `crop_id` in place of the names.
- Bars: Tab moves between them, Enter/Space selects; the selected bar has a visible outline.

## Left to the builder

- Component file names and split (beyond `WeekBars` being the only client component with state).
- Which shadcn components to add (alert and badge are the likely ones), as long as they're restyled to the tokens.
- Exact skeleton look; README wording.
