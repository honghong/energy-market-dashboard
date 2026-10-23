import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SpreadHistory, SpreadInfo } from "../api";
import { describeZ, formatDate, formatSigned } from "../format";
import { LineTooltip, type TooltipRow } from "./LineTooltip";

interface Props {
  spreads: SpreadInfo[];
  selected: string;
  onSelect: (id: string) => void;
  history: SpreadHistory | null;
}

export function SpreadPanel({ spreads, selected, onSelect, history }: Props) {
  const info = spreads.find((s) => s.id === selected);
  const points = history?.points ?? [];
  // Draw a zero line only when the spread actually crosses zero in the visible window.
  const crossesZero = points.some((p) => p.value < 0) && points.some((p) => p.value > 0);
  const last = points.at(-1);
  const z = describeZ(last?.zscore);
  const window = history?.window ?? 60;
  const fmt = (v: number) => `$${v.toFixed(2)}`;
  const rows: TooltipRow[] = [
    { key: "value", label: "Spread", color: "var(--series-1)", format: fmt },
    { key: "mean", label: `${window}-day avg`, color: "var(--series-2)", format: fmt },
    { key: "zscore", label: "Z-score", color: "transparent", format: (v) => formatSigned(v) },
  ];

  return (
    <section className="panel" aria-labelledby="spread-title">
      <header className="panel__head">
        <div>
          <h2 id="spread-title">Spreads</h2>
          <p className="panel__sub">{info?.description}</p>
        </div>
        <div className="segmented" role="tablist" aria-label="Spread">
          {spreads.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={s.id === selected}
              onClick={() => onSelect(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
      </header>

      <div className="spread-stats">
        <div>
          <span className="stat-label">Latest</span>
          <span className="stat-value">{last ? fmt(last.value) : "–"}</span>
          <span className="stat-note">{history?.unit}</span>
        </div>
        <div>
          <span className="stat-label">{window}-day average</span>
          <span className="stat-value">{last?.mean == null ? "–" : fmt(last.mean)}</span>
        </div>
        <div>
          <span className="stat-label">Z-score</span>
          <span className="stat-value">{formatSigned(last?.zscore)}</span>
          <span className={`badge badge--${z.tone}`}>{z.label}</span>
        </div>
      </div>

      <ul className="legend" aria-label="Legend">
        {rows.slice(0, 2).map((r) => (
          <li key={r.key}>
            <span className="swatch" style={{ background: r.color }} aria-hidden="true" />
            {r.label}
          </li>
        ))}
      </ul>

      <div className="chart" role="img" aria-label={`${info?.name ?? "Spread"} chart`}>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => formatDate(d)}
              minTickGap={48}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--axis)" }}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              width={56}
              tickFormatter={fmt}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            {crossesZero && <ReferenceLine y={0} stroke="var(--axis)" />}
            <Tooltip
              content={<LineTooltip rows={rows} />}
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
            />
            <Line type="monotone" dataKey="mean" stroke="var(--series-2)" strokeWidth={2}
              strokeDasharray="5 4" dot={false} isAnimationActive={false} connectNulls
              activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }} />
            <Line type="monotone" dataKey="value" stroke="var(--series-1)" strokeWidth={2}
              dot={false} isAnimationActive={false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
