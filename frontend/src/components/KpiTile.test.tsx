import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Summary } from "../api";
import { KpiTile } from "./KpiTile";

const summary: Summary = {
  series_id: "wti",
  name: "WTI Crude (Cushing)",
  unit: "$/bbl",
  last_date: "2026-10-16",
  last: 71.42,
  change: -0.58,
  change_pct: -0.8055,
  ma20: 72.1,
  ma50: 70.3,
  vol_20d_annualized: 0.284,
  high_52w: 82.1,
  low_52w: 61.9,
  ytd_pct: 4.2,
};

describe("KpiTile", () => {
  it("shows price, signed change and volatility", () => {
    render(<KpiTile summary={summary} market="Crude oil" selected={false} onSelect={() => {}} />);
    expect(screen.getByText("$71.42")).toBeTruthy();
    expect(screen.getByText(/−0\.58/)).toBeTruthy();
    expect(screen.getByText(/20d vol 28%/)).toBeTruthy();
    expect(screen.getByRole("button").getAttribute("aria-pressed")).toBe("false");
  });

  it("selects the series on click", () => {
    const onSelect = vi.fn();
    render(<KpiTile summary={summary} market="Crude oil" selected onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledWith("wti");
  });
});
