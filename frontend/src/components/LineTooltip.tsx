import type { TooltipProps } from "recharts";
import { formatDate } from "../format";

export interface TooltipRow {
  key: string;
  label: string;
  color: string;
  format: (v: number) => string;
}

/** Crosshair tooltip: date header, then one row per series with a colored key. */
export function LineTooltip({
  active,
  payload,
  label,
  rows,
}: TooltipProps<number, string> & { rows: TooltipRow[] }) {
  if (!active || !payload?.length) return null;
  const datum = payload[0].payload as Record<string, number | null>;
  return (
    <div className="tooltip" role="status">
      <div className="tooltip__date">{formatDate(String(label), "long")}</div>
      {rows.map((r) => {
        const v = datum[r.key];
        return (
          <div className="tooltip__row" key={r.key}>
            <span className="swatch" style={{ background: r.color }} aria-hidden="true" />
            <span className="tooltip__label">{r.label}</span>
            <span className="tooltip__value">{v == null ? "–" : r.format(v)}</span>
          </div>
        );
      })}
    </div>
  );
}
