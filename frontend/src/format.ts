// Formatting and date-range helpers (pure functions, unit-tested).

export type RangeKey = "3M" | "6M" | "1Y" | "3Y" | "ALL";

export const RANGES: { key: RangeKey; label: string; months: number | null }[] = [
  { key: "3M", label: "3M", months: 3 },
  { key: "6M", label: "6M", months: 6 },
  { key: "1Y", label: "1Y", months: 12 },
  { key: "3Y", label: "3Y", months: 36 },
  { key: "ALL", label: "All", months: null },
];

/** ISO start date for a range preset, counted back from the latest data date. */
export function rangeStart(key: RangeKey, latest: string | null | undefined): string | undefined {
  const preset = RANGES.find((r) => r.key === key);
  if (!preset?.months || !latest) return undefined;
  const d = new Date(`${latest}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - preset.months);
  return d.toISOString().slice(0, 10);
}

/** Price precision depends on the unit: $/gal trades in tenths of a cent. */
export function decimalsFor(unit: string): number {
  return unit === "$/gal" ? 3 : 2;
}

export function formatPrice(value: number | null | undefined, unit: string): string {
  if (value == null || Number.isNaN(value)) return "–";
  return `$${value.toFixed(decimalsFor(unit))}`;
}

export function formatSigned(value: number | null | undefined, digits = 2, suffix = ""): string {
  if (value == null || Number.isNaN(value)) return "–";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}${suffix}`;
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  return formatSigned(value, digits, "%");
}

export function formatDate(iso: string, style: "short" | "long" = "short"): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: style === "long" ? "numeric" : undefined,
    year: style === "long" ? "numeric" : "2-digit",
  });
}

/** Plain-language read of a spread z-score. */
export function describeZ(z: number | null | undefined): { label: string; tone: "neutral" | "high" | "low" } {
  if (z == null || Number.isNaN(z)) return { label: "Not enough history", tone: "neutral" };
  if (z >= 2) return { label: "Unusually wide", tone: "high" };
  if (z <= -2) return { label: "Unusually narrow", tone: "low" };
  return { label: "Within normal range", tone: "neutral" };
}

/** Position of `value` inside [low, high] as 0..1, for the 52-week range bar. */
export function rangePosition(value: number, low: number, high: number): number {
  if (high <= low) return 0.5;
  return Math.min(1, Math.max(0, (value - low) / (high - low)));
}
