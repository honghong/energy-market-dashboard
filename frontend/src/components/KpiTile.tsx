import type { Summary } from "../api";
import { formatPct, formatPrice, formatSigned, decimalsFor, rangePosition } from "../format";

interface Props {
  summary: Summary;
  market: string;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function KpiTile({ summary: s, market, selected, onSelect }: Props) {
  const dir = s.change == null ? 0 : Math.sign(s.change);
  const arrow = dir > 0 ? "▲" : dir < 0 ? "▼" : "•";
  const pos = rangePosition(s.last, s.low_52w, s.high_52w);

  return (
    <button
      type="button"
      className={`tile${selected ? " tile--selected" : ""}`}
      aria-pressed={selected}
      onClick={() => onSelect(s.series_id)}
    >
      <span className="tile__market">{market}</span>
      <span className="tile__name">{s.name}</span>
      <span className="tile__value">
        {formatPrice(s.last, s.unit)}
        <span className="tile__unit">{s.unit.replace("$", "")}</span>
      </span>
      <span className="tile__change" aria-label={`Day change ${formatPct(s.change_pct, 2)}`}>
        <span aria-hidden="true">{arrow}</span> {formatSigned(s.change, decimalsFor(s.unit))} (
        {formatPct(s.change_pct, 2)})
      </span>
      <span className="tile__range" title="Position within the 52-week range">
        <span className="tile__range-label">{formatPrice(s.low_52w, s.unit)}</span>
        <span className="tile__range-track">
          <span className="tile__range-dot" style={{ left: `${pos * 100}%` }} />
        </span>
        <span className="tile__range-label">{formatPrice(s.high_52w, s.unit)}</span>
      </span>
      <span className="tile__meta">
        20d vol{" "}
        {s.vol_20d_annualized == null ? "–" : `${(s.vol_20d_annualized * 100).toFixed(0)}%`} · YTD{" "}
        {formatPct(s.ytd_pct)}
      </span>
    </button>
  );
}
