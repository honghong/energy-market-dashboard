"""Extract-load pipeline: pull each series incrementally and upsert into the database.

Run from the command line:
    python -m app.pipeline                 # source from env (EIA if a key is set, else sample)
    python -m app.pipeline --source sample
    python -m app.pipeline --full-refresh  # re-pull from HISTORY_START
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.catalog import SERIES, SeriesDef
from app.config import Settings, get_settings
from app.models import IngestRun, PriceObservation
from app.sources import Observation, PriceSource

log = logging.getLogger(__name__)

UPSERT_BATCH = 1000


def build_source(settings: Settings, name: str | None = None) -> PriceSource:
    name = name or settings.resolved_source
    if name == "eia":
        from app.sources.eia import EIAClient

        return EIAClient(settings.eia_api_key or "")
    if name == "sample":
        from app.sources.sample import SampleSource

        return SampleSource()
    raise ValueError(f"Unknown data source: {name!r}")


def _insert_for(session: Session):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover
        raise RuntimeError(f"Upsert not implemented for {dialect}")
    return insert


def upsert(session: Session, rows: list[Observation], source: str) -> int:
    """Insert new observations and overwrite revised values. Returns rows written."""
    if not rows:
        return 0
    insert = _insert_for(session)
    now = datetime.now(UTC)
    written = 0
    for i in range(0, len(rows), UPSERT_BATCH):
        chunk = rows[i : i + UPSERT_BATCH]
        stmt = insert(PriceObservation).values(
            [
                {
                    "series_id": r.series_id,
                    "period": r.period,
                    "value": r.value,
                    "source": source,
                    "loaded_at": now,
                }
                for r in chunk
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "period"],
            set_={
                "value": stmt.excluded.value,
                "source": stmt.excluded.source,
                "loaded_at": stmt.excluded.loaded_at,
            },
        )
        session.execute(stmt)
        written += len(chunk)
    return written


def start_date_for(
    session: Session, series: SeriesDef, settings: Settings, full_refresh: bool
) -> date:
    if full_refresh:
        return settings.history_start
    latest = session.scalar(
        select(func.max(PriceObservation.period)).where(PriceObservation.series_id == series.id)
    )
    if latest is None:
        return settings.history_start
    return max(settings.history_start, latest - timedelta(days=settings.revision_lookback_days))


def run_ingest(
    session_factory: sessionmaker,
    source: PriceSource,
    settings: Settings | None = None,
    full_refresh: bool = False,
) -> IngestRun:
    settings = settings or get_settings()
    with session_factory() as session:
        run = IngestRun(source=source.name, started_at=datetime.now(UTC), status="running")
        session.add(run)
        session.commit()

        total = 0
        details: list[str] = []
        failed: list[str] = []
        for series in SERIES:
            try:
                start = start_date_for(session, series, settings, full_refresh)
                rows = source.fetch(series, start)
                n = upsert(session, rows, source.name)
                session.commit()
                total += n
                details.append(f"{series.id}: {n} rows from {start.isoformat()}")
                log.info("%s: upserted %d rows from %s", series.id, n, start)
            except Exception as exc:  # one bad series must not sink the whole run
                session.rollback()
                failed.append(series.id)
                details.append(f"{series.id}: FAILED ({exc})")
                log.exception("Ingest failed for %s", series.id)

        run.finished_at = datetime.now(UTC)
        run.rows_upserted = total
        if not failed:
            run.status = "success"
        elif len(failed) < len(SERIES):
            run.status = "partial"
        else:
            run.status = "failed"
        run.detail = "\n".join(details)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load energy price history into the database")
    parser.add_argument("--source", choices=["eia", "sample"], default=None)
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from app.db import Database

    settings = get_settings()
    db = Database(settings.database_url)
    db.create_all()
    run = run_ingest(
        db.SessionLocal, build_source(settings, args.source), settings, args.full_refresh
    )
    print(f"Run {run.id}: {run.status}, {run.rows_upserted} rows\n{run.detail}")
    return 0 if run.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
