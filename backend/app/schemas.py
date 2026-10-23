"""API response models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class SeriesInfo(BaseModel):
    id: str
    name: str
    market: str
    unit: str
    first_date: date | None
    last_date: date | None
    observations: int


class SpreadInfo(BaseModel):
    id: str
    name: str
    unit: str
    description: str


class Catalog(BaseModel):
    data_source: str
    is_sample: bool
    series: list[SeriesInfo]
    spreads: list[SpreadInfo]


class PricePoint(BaseModel):
    date: date
    price: float
    ma20: float | None
    ma50: float | None


class PriceHistory(BaseModel):
    series_id: str
    unit: str
    points: list[PricePoint]


class Summary(BaseModel):
    series_id: str
    name: str
    unit: str
    last_date: date
    last: float
    change: float | None
    change_pct: float | None
    ma20: float | None
    ma50: float | None
    vol_20d_annualized: float | None
    high_52w: float
    low_52w: float
    ytd_pct: float | None


class SpreadPoint(BaseModel):
    date: date
    value: float
    mean: float | None
    zscore: float | None


class SpreadHistory(BaseModel):
    spread_id: str
    unit: str
    window: int
    points: list[SpreadPoint]


class IngestRunOut(BaseModel):
    id: int
    source: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_upserted: int
    detail: str | None

    model_config = {"from_attributes": True}
