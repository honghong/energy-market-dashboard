"""Synthetic price generator for running the dashboard without an EIA API key.

The numbers are simulated (correlated random walks around realistic levels) and are
NOT market data. The UI labels them as sample data whenever this source is used.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.catalog import SeriesDef
from app.sources import Observation

_ANCHOR = date(2015, 1, 1)


def _business_days(start: date, end: date) -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, end=end)


def simulate(end: date, seed: int = 7) -> pd.DataFrame:
    """Simulate a deterministic daily panel from a fixed anchor date to `end`."""
    idx = _business_days(_ANCHOR, end)
    n = len(idx)
    rng = np.random.default_rng(seed)

    # Crude: mean-reverting log price around ~$70 with 30% annualized vol.
    shocks = rng.normal(0, 0.30 / np.sqrt(252), n)
    log_wti = np.empty(n)
    log_wti[0] = np.log(55.0)
    for i in range(1, n):
        log_wti[i] = log_wti[i - 1] + 0.004 * (np.log(70.0) - log_wti[i - 1]) + shocks[i]
    wti = np.exp(log_wti)

    # Brent-WTI spread: mean-reverting around $4.
    spread = np.empty(n)
    spread[0] = 3.5
    for i in range(1, n):
        spread[i] = spread[i - 1] + 0.05 * (4.0 - spread[i - 1]) + rng.normal(0, 0.35)
    brent = wti + spread

    # Refined products: crude/42 plus a seasonal crack (gasoline peaks in summer).
    doy = idx.dayofyear.to_numpy()
    season = np.sin(2 * np.pi * (doy - 80) / 365.25)
    gas_crack = 22 + 8 * season + np.cumsum(rng.normal(0, 0.6, n)) * 0.05
    dist_crack = 30 - 4 * season + np.cumsum(rng.normal(0, 0.6, n)) * 0.05
    rbob = (wti + gas_crack) / 42 + rng.normal(0, 0.02, n)
    ulsd = (wti + dist_crack) / 42 + rng.normal(0, 0.02, n)

    # Henry Hub: winter-seasonal, high vol, floored.
    hh_shocks = rng.normal(0, 0.55 / np.sqrt(252), n)
    log_hh = np.empty(n)
    log_hh[0] = np.log(3.0)
    winter = 0.25 * np.cos(2 * np.pi * (doy - 15) / 365.25)
    for i in range(1, n):
        target = np.log(3.0) + winter[i]
        log_hh[i] = log_hh[i - 1] + 0.01 * (target - log_hh[i - 1]) + hh_shocks[i]
    henry_hub = np.maximum(np.exp(log_hh), 1.2)

    return pd.DataFrame(
        {
            "wti": wti.round(2),
            "brent": brent.round(2),
            "henry_hub": henry_hub.round(2),
            "rbob_nyh": rbob.round(3),
            "ulsd_nyh": ulsd.round(3),
        },
        index=idx,
    )


class SampleSource:
    name = "sample"

    def __init__(self, today: date | None = None, seed: int = 7) -> None:
        # Stop at the previous business day, like a real end-of-day feed.
        self.end = (today or date.today()) - timedelta(days=1)
        self._panel = simulate(self.end, seed)

    def fetch(self, series: SeriesDef, start: date, end: date | None = None) -> list[Observation]:
        col = self._panel[series.id]
        mask = col.index >= pd.Timestamp(start)
        if end:
            mask &= col.index <= pd.Timestamp(end)
        return [Observation(series.id, ts.date(), float(v)) for ts, v in col[mask].items()]
