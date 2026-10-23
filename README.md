# Energy Market Dashboard

A full-stack data application for tracking energy commodity prices. A Python pipeline pulls daily prices for crude oil, natural gas and refined products from the U.S. Energy Information Administration (EIA) and loads them into PostgreSQL. A FastAPI service computes the analytics with Pandas, and a React + TypeScript front end displays prices, trends, spreads and pipeline health.

**Live demo:** _add your Azure URL here after the first deploy_

![Dashboard screenshot](docs/dashboard-light.png)

> The screenshot shows the built-in **sample data** mode (simulated prices, clearly labeled in the UI). With a free EIA API key the same app runs on real EIA prices.

## What it does

| Area | Details |
|---|---|
| **Markets** | WTI Cushing, Brent, Henry Hub natural gas, NY Harbor RBOB gasoline, NY Harbor ULSD |
| **Price analytics** | Last price, day change, 20- and 50-day moving averages, 20-day annualized volatility, 52-week range, YTD change |
| **Spreads** | Brent–WTI spread and the 3-2-1 crack spread (a refining-margin proxy), each with a 60-day rolling mean and z-score that flags unusually wide or narrow spreads |
| **Data pipeline** | Incremental loads with a revision lookback (EIA revises recent prints), idempotent upserts, per-series failure isolation, and a run log shown in the UI |
| **UI** | KPI tiles, interactive charts with crosshair tooltips, range presets (3M–All), a table view for accessibility, light and dark themes, mobile layout |

## Architecture

```mermaid
flowchart LR
    EIA[EIA Open Data API v2] -->|httpx, paging, retries| P[Python pipeline]
    S[Sample simulator] -.->|no API key| P
    P -->|upsert| DB[(PostgreSQL)]
    DB --> API[FastAPI + Pandas analytics]
    API -->|JSON /api| UI[React + TypeScript + Recharts]
    SCHED[In-process scheduler / CLI / POST /api/pipeline/run] --> P
```

```
backend/
  app/
    catalog.py        series and spread definitions (EIA route + series id)
    sources/eia.py    EIA API v2 client: pagination, retry with backoff, error handling
    sources/sample.py deterministic simulator for offline demos
    pipeline.py       incremental extract-load, dialect-aware upsert, run audit log, CLI
    analytics.py      Pandas: moving averages, volatility, spreads, z-scores
    main.py           FastAPI routes and optional background scheduler
  tests/              pytest: EIA client (mocked HTTP), pipeline, analytics math, API
frontend/
  src/                React components, typed API client, formatting helpers, Vitest tests
infra/main.bicep      Azure: Container Apps, scheduled Job, PostgreSQL, Key Vault, managed identity
Dockerfile            single-container image (API + built UI) used on Azure
docker-compose.yml    local stack: PostgreSQL + API + nginx-served UI
.github/workflows/    CI (ruff, pytest, PostgreSQL smoke test, typecheck, Vitest, builds) and Azure deploy
```

### Design notes

- **Incremental and idempotent loads.** Each run starts at the latest stored date minus `REVISION_LOOKBACK_DAYS`, and `INSERT … ON CONFLICT DO UPDATE` overwrites revised values instead of duplicating them. Re-running the pipeline is always safe.
- **Failure isolation.** Each series loads in its own transaction. If one EIA dataset is down, the run is marked `partial` and the other series still load.
- **Warm rolling windows.** The API loads extra history before the requested start date, so moving averages and z-scores are populated from the first visible day.
- **Cloud deployment as code.** Bicep defines every Azure resource. Deploys use OIDC (no stored credentials), images are built inside Azure Container Registry, and the app reads its secrets from Key Vault through a managed identity.
- **Portable storage.** SQLAlchemy 2 runs on PostgreSQL in Docker and on SQLite for local development and tests.
- **Accessible charts.** The colors come from a color-blind-validated palette with separate light and dark steps. Every chart has a legend and a table view, and status is shown with an icon and a label, never color alone.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness and database check |
| GET | `/api/catalog` | Series and spreads with data coverage; flags sample data |
| GET | `/api/summaries` | Headline stats for every series |
| GET | `/api/series/{id}/prices?start=&end=` | Daily prices with 20- and 50-day moving averages |
| GET | `/api/spreads/{id}?start=&end=&window=` | Spread values, rolling mean and z-score |
| GET | `/api/pipeline/runs?limit=` | Recent ingestion runs |
| POST | `/api/pipeline/run` | Trigger an ingest (requires `X-Pipeline-Token`) |

Interactive docs are served at `http://localhost:8000/docs`.

## Run it

### With Docker

```bash
cp .env.example .env          # optionally add EIA_API_KEY (free: https://www.eia.gov/opendata/register.php)
docker compose up --build
```

Open http://localhost:8080. The API loads data on startup and refreshes every 6 hours. Without a key, it uses simulated sample data.

### On Azure

Azure Container Apps hosts the app, Azure Database for PostgreSQL stores the data, a scheduled Container Apps Job runs ingestion, and Key Vault holds the secrets behind a managed identity. GitHub Actions deploys it with OIDC and Bicep. See **[docs/azure-deploy.md](docs/azure-deploy.md)** for the one-time setup.

### Locally

```bash
# Backend (Python 3.12+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.pipeline --source sample      # or: EIA_API_KEY=... python -m app.pipeline
uvicorn app.main:app --reload               # http://localhost:8000/docs

# Frontend (Node 22)
cd frontend
npm install
npm run dev                                  # http://localhost:5173, proxies /api to :8000
```

### Tests

```bash
cd backend && ruff check . && pytest        # 27 tests
cd frontend && npm run typecheck && npm test
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./energy.db` | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host/db` |
| `EIA_API_KEY` | – | Enables the live EIA source |
| `DATA_SOURCE` | `eia` if key set, else `sample` | Force a source |
| `HISTORY_START` | `2019-01-01` | First date loaded on an empty database |
| `REVISION_LOOKBACK_DAYS` | `10` | Days re-read on each incremental run |
| `INGEST_INTERVAL_MINUTES` | `0` (off) | Background refresh interval inside the API |
| `PIPELINE_TOKEN` | – | Enables `POST /api/pipeline/run` |
| `STATIC_DIR` | – | Serve the built React app from FastAPI (set in the single-container image) |

## Data source

Prices come from the [EIA Open Data API v2](https://www.eia.gov/opendata/): spot prices (`petroleum/pri/spt`) and Henry Hub (`natural-gas/pri/fut`). Series IDs live in `backend/app/catalog.py`, so adding a market is a one-line change. EIA data is public domain. The sample mode generates simulated prices for demos and is never presented as market data.
