import { describe, expect, it } from "vitest";
import {
  describeZ,
  formatPct,
  formatPrice,
  formatSigned,
  rangePosition,
  rangeStart,
} from "./format";

describe("rangeStart", () => {
  it("counts back from the latest data date", () => {
    expect(rangeStart("3M", "2026-10-16")).toBe("2026-07-16");
    expect(rangeStart("1Y", "2026-10-16")).toBe("2025-10-16");
  });
  it("returns undefined for All or missing data", () => {
    expect(rangeStart("ALL", "2026-10-16")).toBeUndefined();
    expect(rangeStart("1Y", undefined)).toBeUndefined();
  });
});

describe("number formatting", () => {
  it("uses 3 decimals for $/gal and 2 otherwise", () => {
    expect(formatPrice(2.3456, "$/gal")).toBe("$2.346");
    expect(formatPrice(71.2, "$/bbl")).toBe("$71.20");
    expect(formatPrice(null, "$/bbl")).toBe("–");
  });
  it("signs values with a true minus", () => {
    expect(formatSigned(1.5)).toBe("+1.50");
    expect(formatSigned(-1.5)).toBe("−1.50");
    expect(formatPct(-0.04, 2)).toBe("−0.04%");
  });
});

describe("describeZ", () => {
  it("flags stretched spreads", () => {
    expect(describeZ(2.4).tone).toBe("high");
    expect(describeZ(-2.1).tone).toBe("low");
    expect(describeZ(0.3).label).toBe("Within normal range");
    expect(describeZ(null).tone).toBe("neutral");
  });
});

describe("rangePosition", () => {
  it("clamps to the 52-week range", () => {
    expect(rangePosition(75, 50, 100)).toBe(0.5);
    expect(rangePosition(120, 50, 100)).toBe(1);
    expect(rangePosition(5, 5, 5)).toBe(0.5);
  });
});
