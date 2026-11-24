export type TimeFormat = "12h" | "24h";

const pad = (value: number) => value.toString().padStart(2, "0");

export function parseLocal(iso: string): Date {
  return new Date(iso);
}

export function fmtTime(iso: string, format: TimeFormat = "24h"): string {
  const date = parseLocal(iso);
  if (Number.isNaN(date.getTime())) return "—";
  if (format === "12h") {
    const hour = date.getHours() % 12 || 12;
    return `${hour}:${pad(date.getMinutes())} ${date.getHours() < 12 ? "AM" : "PM"}`;
  }
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fmtTimeRange(startIso: string, endIso: string, format: TimeFormat = "24h"): string {
  return `${fmtTime(startIso, format)}–${fmtTime(endIso, format)}`;
}

export function fmtDate(
  value: string,
  options: Intl.DateTimeFormatOptions = { weekday: "short", day: "numeric", month: "short" },
): string {
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : parseLocal(value);
  return new Intl.DateTimeFormat(undefined, options).format(date);
}

export function todayISO(): string {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function toISODate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function addDaysISO(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + days);
  return toISODate(date);
}

export function startOfWeekISO(iso: string, weekStart: "monday" | "sunday" = "monday"): string {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const weekday = date.getDay(); // 0 Sun
  const offset = weekStart === "monday" ? (weekday + 6) % 7 : weekday;
  date.setDate(date.getDate() - offset);
  return toISODate(date);
}

export function weekDates(startISO: string): string[] {
  return Array.from({ length: 7 }, (_, index) => addDaysISO(startISO, index));
}

export function fmtWeekRange(startISO: string): string {
  const endISO = addDaysISO(startISO, 6);
  const start = new Date(`${startISO}T00:00:00`);
  const end = new Date(`${endISO}T00:00:00`);
  const sameMonth = start.getMonth() === end.getMonth();
  const startLabel = new Intl.DateTimeFormat(undefined, { day: "numeric", month: sameMonth ? undefined : "short" }).format(start);
  const endLabel = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(end);
  return `${startLabel} – ${endLabel}`;
}

export function fmtDateTime(iso: string, format: TimeFormat = "24h"): string {
  return `${fmtDate(iso, { day: "numeric", month: "short" })} · ${fmtTime(iso, format)}`;
}

export function durationLabel(minutes: number): string {
  if (minutes <= 0) return "0m";
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest}m`;
  if (!rest) return `${hours}h`;
  return `${hours}h ${rest}m`;
}

export function relativeTime(iso: string): string {
  const then = parseLocal(iso).getTime();
  const diff = Date.now() - then;
  if (Number.isNaN(diff)) return "";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return fmtDate(iso, { day: "numeric", month: "short" });
}

export function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function isoLocalFromParts(dateISO: string, timeHHMM: string): string {
  return `${dateISO}T${timeHHMM}:00`;
}

export function timeInputValue(iso: string): string {
  const date = parseLocal(iso);
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function dateInputValue(iso: string): string {
  const date = parseLocal(iso);
  return toISODate(date);
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
