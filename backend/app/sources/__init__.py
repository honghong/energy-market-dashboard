"""Data sources. Each returns rows of (series_id, period, value)."""

from __future__ import annotations

from datetime import date
from typing import NamedTuple, Protocol

from app.catalog import SeriesDef


class Observation(NamedTuple):
    series_id: str
    period: date
    value: float


class PriceSource(Protocol):
    name: str

    def fetch(
        self, series: SeriesDef, start: date, end: date | None = None
    ) -> list[Observation]: ...
