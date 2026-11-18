// How numbers and dates read on screen. Plan dates are the plot's local calendar dates ("YYYY-MM-DD"):
// they are formatted as plain dates, never shifted by the server's time zone.

function plainDate(iso: string): Date {
  return new Date(`${iso}T00:00:00Z`);
}

function dateFormat(options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("en-GB", { ...options, timeZone: "UTC" });
}

const SHORT = dateFormat({ weekday: "short", day: "numeric", month: "short" });
const WEEKDAY = dateFormat({ weekday: "short" });
const LONG = dateFormat({ weekday: "long", day: "numeric", month: "long" });
const LITRES = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const MM = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

/** "38 minutes", "1 minute", "1 h 05 min", "2 h". */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return minutes === 1 ? "1 minute" : `${minutes} minutes`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")} min`;
}

/** Bar labels, hours:minutes: "1:53", "0:41". */
export function formatClock(minutes: number): string {
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

export const formatLitres = (litres: number) => LITRES.format(litres);
export const formatMm = (mm: number) => MM.format(mm);
export const formatDayShort = (iso: string) => SHORT.format(plainDate(iso)).replace(",", "");
export const formatWeekday = (iso: string) => WEEKDAY.format(plainDate(iso));
export const formatDayLong = (iso: string) => LONG.format(plainDate(iso)).replace(",", "");

/** How old a forecast is: "35 min", "11 h". */
export function formatAge(fetchedAtIso: string, now: Date): string {
  const minutes = Math.max(1, Math.round((now.getTime() - new Date(fetchedAtIso).getTime()) / 60000));
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h`;
}
