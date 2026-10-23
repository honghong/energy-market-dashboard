from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.pipeline import run_ingest
from app.sources.sample import SampleSource


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        data_source="sample",
        history_start=date(2024, 1, 1),
        pipeline_token="secret",
    )


@pytest.fixture
def db(settings: Settings) -> Database:
    database = Database(settings.database_url)
    database.create_all()
    return database


@pytest.fixture
def sample_source() -> SampleSource:
    return SampleSource(today=date(2026, 10, 20))


@pytest.fixture
def client(settings: Settings, sample_source: SampleSource):
    app = create_app(settings, source_factory=lambda: sample_source)
    with TestClient(app) as c:
        run_ingest(app.state.db.SessionLocal, sample_source, settings)
        yield c
