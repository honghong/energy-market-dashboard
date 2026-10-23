import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceHistory } from "../api";
import { formatDate, formatPrice } from "../format";
import { LineTooltip, type TooltipRow } from "./LineTooltip";

interface Props {
  title: string;
  history: PriceHistory | null;
  loading: boolean;
}

export function PriceChart({ title, history, loading }: Props) {
  const [showTable, setShowTable] = useState(false);
  const unit = history?.unit ?? "$/bbl";
  const fmt = (v: number) => formatPrice(v, unit);
  const rows: TooltipRow[] = [
    { key: "price", label: "Price", color: "var(--series-1)", format: fmt },
    { key: "ma20", label: "20-day avg", color: "var(--series-2)", format: fmt },
    { key: "ma50", label: "50-day avg", color: "var(--series-3)", format: fmt },
  ];
  const points = history?.points ?? [];

  return (
    <section className="panel" aria-labelledby="price-title">
      <header className="panel__head">
        <div>
          <h2 id="price-title">{title}</h2>
          <p className="panel__sub">Daily settlement with 20- and 50-day moving averages, {unit}</p>
        </div>
        <button type="button" className="link-btn" onClick={() => setShowTable((s) => !s)}>
          {showTable ? "Show chart" : "Show table"}
        </button>
      </header>

      {!showTable && (
      <ul className="legend" aria-label="Legend">
        {rows.map((r) => (
          <li key={r.key}>
            <span className="swatch" style={{ background: r.color }} aria-hidden="true" />
            {r.label}
          </li>
        ))}
      </ul>
      )}

      {loading && !points.length ? (
        <div className="chart-placeholder">Loading…</div>
      ) : showTable ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                {rows.map((r) => (
                  <th scope="col" key={r.key} className="num">
                    {r.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points
                .slice(-30)
                .reverse()
                .map((p) => (
                  <tr key={p.date}>
                    <td>{formatDate(p.date, "long")}</td>
                    <td className="num">{fmt(p.price)}</td>
                    <td className="num">{p.ma20 == null ? "–" : fmt(p.ma20)}</td>
                    <td className="num">{p.ma50 == null ? "–" : fmt(p.ma50)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="chart" role="img" aria-label={`${title} price chart`}>
          <ResponsiveContainer width="100%" height={320}>
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
                tickFormatter={(v: number) => fmt(v)}
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<LineTooltip rows={rows} />}
                cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              />
              <Line type="monotone" dataKey="ma50" stroke="var(--series-3)" strokeWidth={2}
                dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
                isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="ma20" stroke="var(--series-2)" strokeWidth={2}
                dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--surface)" }}
                isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="price" stroke="var(--series-1)" strokeWidth={2}
                dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }}
                isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
