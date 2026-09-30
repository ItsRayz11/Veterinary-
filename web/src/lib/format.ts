import type { Dose } from "./api";

const trim = (n: string) => (n.includes(".") ? n.replace(/\.?0+$/, "") : n);

export function formatDoseRange(d: Pick<Dose, "dose_min" | "dose_max" | "dose_unit">): string {
  const lo = trim(d.dose_min);
  const hi = trim(d.dose_max);
  return lo === hi ? `${lo} ${d.dose_unit}` : `${lo}–${hi} ${d.dose_unit}`;
}

export function formatFrequency(hours: string | null): string {
  return hours ? `q${trim(hours)}h` : "–";
}

export function formatDuration(d: Pick<Dose, "duration_min_days" | "duration_max_days">): string {
  const { duration_min_days: a, duration_max_days: b } = d;
  if (a == null && b == null) return "–";
  if (a === b || b == null) return `${a} d`;
  if (a == null) return `up to ${b} d`;
  return `${a}–${b} d`;
}

export function formatDate(iso: string | null): string {
  return iso ? new Date(iso).toISOString().slice(0, 10) : "not reviewed";
}
