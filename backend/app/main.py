"""FastAPI application: REST endpoints over the stored prices and analytics."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import analytics
from app.catalog import SERIES, SERIES_BY_ID, SPREADS, SPREADS_BY_ID
from app.config import Settings, get_settings
from app.db import Database
from app.models import IngestRun, PriceObservation
from app.pipeline import build_source, run_ingest
from app.schemas import (
    Catalog,
    IngestRunOut,
    PriceHistory,
    PricePoint,
    SeriesInfo,
    SpreadHistory,
    SpreadInfo,
    SpreadPoint,
    Summary,
)
from app.sources import PriceSource

log = logging.getLogger(__name__)

# Extra history loaded before `start` so rolling windows are warm on the first visible day.
WARMUP_DAYS = 120


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


SessionDep = Annotated[Session, Depends(get_session)]


def _clean(value: float) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else value


def create_app(
    settings: Settings | None = None,
    source_factory: Callable[[], PriceSource] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.database_url)
    make_source = source_factory or (lambda: build_source(settings))

    def ingest_once() -> IngestRun:
        return run_ingest(db.SessionLocal, make_source(), settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.create_all()
        task = None
        if settings.ingest_interval_minutes > 0:

            async def scheduler() -> None:
                while True:
                    try:
                        await run_in_threadpool(ingest_once)
                    except Exception:
                        log.exception("Scheduled ingest failed")
                    await asyncio.sleep(settings.ingest_interval_minutes * 60)

            task = asyncio.create_task(scheduler())
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Energy Market Dashboard API", version="1.0.0", lifespan=lifespan)
    app.state.db = db
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health(session: SessionDep) -> dict:
        session.execute(select(1))
        return {"status": "ok"}

    @app.get("/api/catalog", response_model=Catalog)
    def catalog(session: SessionDep) -> Catalog:
        coverage = {
            row.series_id: row
            for row in session.execute(
                select(
                    PriceObservation.series_id,
                    func.min(PriceObservation.period).label("first"),
                    func.max(PriceObservation.period).label("last"),
                    func.count().label("n"),
                ).group_by(PriceObservation.series_id)
            )
        }
        sources = set(session.scalars(select(PriceObservation.source).distinct()))
        data_source = sources.pop() if len(sources) == 1 else ("mixed" if sources else "none")
        return Catalog(
            data_source=data_source,
            is_sample=data_source in ("sample", "mixed"),
            series=[
                SeriesInfo(
                    id=s.id,
                    name=s.name,
                    market=s.market,
                    unit=s.unit,
                    first_date=coverage[s.id].first if s.id in coverage else None,
                    last_date=coverage[s.id].last if s.id in coverage else None,
                    observations=coverage[s.id].n if s.id in coverage else 0,
                )
                for s in SERIES
            ],
            spreads=[SpreadInfo(**vars(sp)) for sp in SPREADS],
        )

    def _series_or_404(series_id: str):
        if series_id not in SERIES_BY_ID:
            raise HTTPException(404, f"Unknown series '{series_id}'")
        return SERIES_BY_ID[series_id]

    @app.get("/api/series/{series_id}/prices", response_model=PriceHistory)
    def prices(
        series_id: str,
        session: SessionDep,
        start: date | None = None,
        end: date | None = None,
    ) -> PriceHistory:
        s = _series_or_404(series_id)
        load_from = start - timedelta(days=WARMUP_DAYS) if start else None
        frame = analytics.load_prices(session, [s.id], load_from, end)
        table = analytics.with_moving_averages(frame[s.id].dropna())
        if start:
            table = table[table.index >= str(start)]
        return PriceHistory(
            series_id=s.id,
            unit=s.unit,
            points=[
                PricePoint(
                    date=ts.date(), price=row.price, ma20=_clean(row.ma20), ma50=_clean(row.ma50)
                )
                for ts, row in table.iterrows()
            ],
        )

    @app.get("/api/summaries", response_model=list[Summary])
    def summaries(session: SessionDep) -> list[Summary]:
        frame = analytics.load_prices(session, [s.id for s in SERIES])
        out: list[Summary] = []
        for s in SERIES:
            stats = analytics.summarize(frame[s.id]) if s.id in frame else {}
            if stats:
                out.append(Summary(series_id=s.id, name=s.name, unit=s.unit, **stats))
        return out

    @app.get("/api/spreads/{spread_id}", response_model=SpreadHistory)
    def spread(
        spread_id: str,
        session: SessionDep,
        start: date | None = None,
        end: date | None = None,
        window: Annotated[int, Query(ge=5, le=250)] = 60,
    ) -> SpreadHistory:
        if spread_id not in SPREADS_BY_ID:
            raise HTTPException(404, f"Unknown spread '{spread_id}'")
        inputs, fn = analytics.SPREAD_INPUTS[spread_id]
        load_from = start - timedelta(days=WARMUP_DAYS) if start else None
        frame = analytics.load_prices(session, inputs, load_from, end)
        table = analytics.with_zscore(fn(frame), window)
        if start:
            table = table[table.index >= str(start)]
        return SpreadHistory(
            spread_id=spread_id,
            unit=SPREADS_BY_ID[spread_id].unit,
            window=window,
            points=[
                SpreadPoint(
                    date=ts.date(),
                    value=row.value,
                    mean=_clean(row["mean"]),
                    zscore=_clean(row.zscore),
                )
                for ts, row in table.iterrows()
            ],
        )

    @app.get("/api/pipeline/runs", response_model=list[IngestRunOut])
    def runs(
        session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 10
    ) -> list[IngestRun]:
        return list(session.scalars(select(IngestRun).order_by(IngestRun.id.desc()).limit(limit)))

    @app.post("/api/pipeline/run", response_model=IngestRunOut)
    def trigger_run(x_pipeline_token: Annotated[str | None, Header()] = None) -> IngestRun:
        if not settings.pipeline_token:
            raise HTTPException(403, "Manual runs are disabled (PIPELINE_TOKEN not set)")
        if x_pipeline_token != settings.pipeline_token:
            raise HTTPException(401, "Invalid pipeline token")
        return ingest_once()

    if settings.static_dir:
        mount_frontend(app, Path(settings.static_dir))

    return app


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built React app from the API container (single-container deployments)."""
    index = static_dir / "index.html"
    if not index.is_file():
        log.warning("STATIC_DIR %s has no index.html; front end not served", static_dir)
        return
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (static_dir / path).resolve()
        if path and candidate.is_file() and static_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)  # client-side routes fall back to the app shell


app = create_app()
