// Typed client for the FastAPI backend.

export interface SeriesInfo {
  id: string;
  name: string;
  market: string;
  unit: string;
  first_date: string | null;
  last_date: string | null;
  observations: number;
}

export interface SpreadInfo {
  id: string;
  name: string;
  unit: string;
  description: string;
}

export interface Catalog {
  data_source: string;
  is_sample: boolean;
  series: SeriesInfo[];
  spreads: SpreadInfo[];
}

export interface PricePoint {
  date: string;
  price: number;
  ma20: number | null;
  ma50: number | null;
}

export interface PriceHistory {
  series_id: string;
  unit: string;
  points: PricePoint[];
}

export interface Summary {
  series_id: string;
  name: string;
  unit: string;
  last_date: string;
  last: number;
  change: number | null;
  change_pct: number | null;
  ma20: number | null;
  ma50: number | null;
  vol_20d_annualized: number | null;
  high_52w: number;
  low_52w: number;
  ytd_pct: number | null;
}

export interface SpreadPoint {
  date: string;
  value: number;
  mean: number | null;
  zscore: number | null;
}

export interface SpreadHistory {
  spread_id: string;
  unit: string;
  window: number;
  points: SpreadPoint[];
}

export interface IngestRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "partial" | "failed";
  rows_upserted: number;
  detail: string | null;
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function get<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v) qs.set(k, v);
  const url = `${BASE}${path}${qs.size ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return (await res.json()) as T;
}

export const api = {
  catalog: () => get<Catalog>("/api/catalog"),
  summaries: () => get<Summary[]>("/api/summaries"),
  prices: (id: string, start?: string) =>
    get<PriceHistory>(`/api/series/${id}/prices`, { start }),
  spread: (id: string, start?: string) => get<SpreadHistory>(`/api/spreads/${id}`, { start }),
  runs: () => get<IngestRun[]>("/api/pipeline/runs", { limit: "8" }),
};
