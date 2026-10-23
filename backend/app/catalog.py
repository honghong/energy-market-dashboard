"""The commodity price series the dashboard tracks, mapped to EIA API v2 routes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeriesDef:
    id: str  # our stable key
    name: str
    market: str
    unit: str
    eia_route: str  # EIA API v2 dataset route
    eia_series: str  # value of the "series" facet within that route


SERIES: tuple[SeriesDef, ...] = (
    SeriesDef("wti", "WTI Crude (Cushing)", "Crude oil", "$/bbl", "petroleum/pri/spt", "RWTC"),
    SeriesDef("brent", "Brent Crude (Europe)", "Crude oil", "$/bbl", "petroleum/pri/spt", "RBRTE"),
    SeriesDef(
        "henry_hub",
        "Henry Hub Natural Gas",
        "Natural gas",
        "$/MMBtu",
        "natural-gas/pri/fut",
        "RNGWHHD",
    ),
    SeriesDef(
        "rbob_nyh",
        "NY Harbor RBOB Gasoline",
        "Refined products",
        "$/gal",
        "petroleum/pri/spt",
        "EER_EPMRR_PF4_Y35NY_DPG",
    ),
    SeriesDef(
        "ulsd_nyh",
        "NY Harbor ULSD",
        "Refined products",
        "$/gal",
        "petroleum/pri/spt",
        "EER_EPD2DXL0_PF4_Y35NY_DPG",
    ),
)

SERIES_BY_ID: dict[str, SeriesDef] = {s.id: s for s in SERIES}


@dataclass(frozen=True)
class SpreadDef:
    id: str
    name: str
    unit: str
    description: str


SPREADS: tuple[SpreadDef, ...] = (
    SpreadDef(
        "brent_wti",
        "Brent–WTI spread",
        "$/bbl",
        "Brent minus WTI: the premium for waterborne crude over US inland crude.",
    ),
    SpreadDef(
        "crack_321",
        "3-2-1 crack spread (NYH)",
        "$/bbl",
        "Refining margin proxy: (2 × RBOB + 1 × ULSD) × 42 − 3 × WTI, per barrel of crude.",
    ),
)

SPREADS_BY_ID: dict[str, SpreadDef] = {s.id: s for s in SPREADS}
