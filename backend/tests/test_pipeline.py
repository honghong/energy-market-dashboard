from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.catalog import SERIES, SeriesDef
from app.models import IngestRun, PriceObservation
from app.pipeline import run_ingest, start_date_for
from app.sources import Observation


class FakeSource:
    name = "fake"

    def __init__(self, data: dict[str, list[Observation]], fail: set[str] | None = None):
        self.data = data
        self.fail = fail or set()
        self.requested: dict[str, date] = {}

    def fetch(self, series: SeriesDef, start: date, end: date | None = None):
        self.requested[series.id] = start
        if series.id in self.fail:
            raise RuntimeError("upstream down")
        return [o for o in self.data.get(series.id, []) if o.period >= start]


def obs(series_id: str, d: str, v: float) -> Observation:
    return Observation(series_id, date.fromisoformat(d), v)


def test_initial_load_then_incremental_with_revision(db, settings):
    source = FakeSource({"wti": [obs("wti", "2026-10-01", 70.0), obs("wti", "2026-10-02", 71.0)]})
    run = run_ingest(db.SessionLocal, source, settings)
    assert run.status == "success"
    assert source.requested["wti"] == settings.history_start

    # Second run: EIA revised 10-02 and published 10-05.
    source.data["wti"] = [obs("wti", "2026-10-02", 71.5), obs("wti", "2026-10-05", 72.0)]
    run_ingest(db.SessionLocal, source, settings)

    # Incremental start = latest stored date minus the revision lookback.
    assert source.requested["wti"] == date(2026, 9, 22)
    with db.SessionLocal() as s:
        values = dict(
            s.execute(
                select(PriceObservation.period, PriceObservation.value).where(
                    PriceObservation.series_id == "wti"
                )
            ).all()
        )
    assert values == {
        date(2026, 10, 1): 70.0,
        date(2026, 10, 2): 71.5,  # revised in place, not duplicated
        date(2026, 10, 5): 72.0,
    }


def test_one_failing_series_marks_run_partial(db, settings):
    source = FakeSource({"wti": [obs("wti", "2026-10-01", 70.0)]}, fail={"brent"})
    run = run_ingest(db.SessionLocal, source, settings)
    assert run.status == "partial"
    assert "brent: FAILED" in run.detail
    assert run.rows_upserted == 1


def test_all_failing_marks_run_failed(db, settings):
    source = FakeSource({}, fail={s.id for s in SERIES})
    assert run_ingest(db.SessionLocal, source, settings).status == "failed"


def test_full_refresh_restarts_from_history_start(db, settings):
    source = FakeSource({"wti": [obs("wti", "2026-10-01", 70.0)]})
    run_ingest(db.SessionLocal, source, settings)
    with db.SessionLocal() as s:
        wti = next(x for x in SERIES if x.id == "wti")
        assert start_date_for(s, wti, settings, full_refresh=True) == settings.history_start


def test_sample_source_loads_every_series(db, settings, sample_source):
    run = run_ingest(db.SessionLocal, sample_source, settings)
    assert run.status == "success"
    with db.SessionLocal() as s:
        counts = dict(
            s.execute(
                select(PriceObservation.series_id, func.count()).group_by(
                    PriceObservation.series_id
                )
            ).all()
        )
        assert set(counts) == {x.id for x in SERIES}
        assert s.scalar(select(func.count()).select_from(IngestRun)) == 1
