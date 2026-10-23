"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./energy.db")
    )
    eia_api_key: str | None = field(default_factory=lambda: os.getenv("EIA_API_KEY") or None)
    # "eia" pulls live data; "sample" generates a synthetic history for offline demos.
    data_source: str = field(default_factory=lambda: os.getenv("DATA_SOURCE", ""))
    history_start: date = field(
        default_factory=lambda: date.fromisoformat(os.getenv("HISTORY_START", "2019-01-01"))
    )
    # EIA revises recent prints, so each incremental run re-reads this many days.
    revision_lookback_days: int = field(
        default_factory=lambda: int(os.getenv("REVISION_LOOKBACK_DAYS", "10"))
    )
    ingest_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("INGEST_INTERVAL_MINUTES", "0"))
    )
    pipeline_token: str | None = field(default_factory=lambda: os.getenv("PIPELINE_TOKEN") or None)
    # Directory holding the built React app; set in the single-container image.
    static_dir: str = field(default_factory=lambda: os.getenv("STATIC_DIR", ""))
    cors_origins: list[str] = field(
        default_factory=lambda: _csv(os.getenv("CORS_ORIGINS", "http://localhost:5173"))
    )

    @property
    def resolved_source(self) -> str:
        if self.data_source:
            return self.data_source
        return "eia" if self.eia_api_key else "sample"


def get_settings() -> Settings:
    return Settings()
