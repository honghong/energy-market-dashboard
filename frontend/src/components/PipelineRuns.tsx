import type { IngestRun } from "../api";

const STATUS: Record<IngestRun["status"], { icon: string; label: string }> = {
  success: { icon: "✓", label: "Success" },
  partial: { icon: "!", label: "Partial" },
  failed: { icon: "✕", label: "Failed" },
  running: { icon: "…", label: "Running" },
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function duration(run: IngestRun): string {
  if (!run.finished_at) return "–";
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function PipelineRuns({ runs }: { runs: IngestRun[] }) {
  return (
    <section className="panel" aria-labelledby="runs-title">
      <header className="panel__head">
        <div>
          <h2 id="runs-title">Data pipeline</h2>
          <p className="panel__sub">Recent ingestion runs (incremental, with revision lookback)</p>
        </div>
      </header>
      {runs.length === 0 ? (
        <p className="empty">No runs yet. Run <code>python -m app.pipeline</code> to load data.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Started</th>
                <th scope="col">Source</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">Rows</th>
                <th scope="col" className="num">Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} title={r.detail ?? undefined}>
                  <td>{when(r.started_at)}</td>
                  <td>{r.source.toUpperCase()}</td>
                  <td>
                    <span className={`status status--${r.status}`}>
                      <span aria-hidden="true" className="status__icon">
                        {STATUS[r.status].icon}
                      </span>
                      {STATUS[r.status].label}
                    </span>
                  </td>
                  <td className="num">{r.rows_upserted.toLocaleString()}</td>
                  <td className="num">{duration(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
