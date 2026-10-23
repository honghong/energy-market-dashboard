"""Pandas analytics over stored prices: moving averages, volatility, spreads, z-scores."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PriceObservation

TRADING_DAYS = 252
BARRELS_PER_GALLON = 42


def load_prices(
    session: Session,
    series_ids: list[str],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Wide frame: one column per series, indexed by date (gaps left as NaN)."""
    stmt = select(PriceObservation.series_id, PriceObservation.period, PriceObservation.value)
    stmt = stmt.where(PriceObservation.series_id.in_(series_ids))
    if start:
        stmt = stmt.where(PriceObservation.period >= start)
    if end:
        stmt = stmt.where(PriceObservation.period <= end)
    rows = session.execute(stmt).all()
    if not rows:
        return pd.DataFrame(columns=series_ids, dtype=float)
    long = pd.DataFrame(rows, columns=["series_id", "period", "value"])
    long["period"] = pd.to_datetime(long["period"])
    wide = long.pivot(index="period", columns="series_id", values="value").sort_index()
    return wide.reindex(columns=series_ids).astype(float)


def with_moving_averages(prices: pd.Series, windows: tuple[int, ...] = (20, 50)) -> pd.DataFrame:
    out = pd.DataFrame({"price": prices})
    for w in windows:
        out[f"ma{w}"] = prices.rolling(w, min_periods=w).mean()
    return out


def annualized_volatility(prices: pd.Series, window: int = 20) -> float | None:
    log_ret = np.log(prices).diff().dropna()
    if len(log_ret) < window:
        return None
    return float(log_ret.iloc[-window:].std(ddof=1) * np.sqrt(TRADING_DAYS))


def summarize(prices: pd.Series) -> dict:
    """Headline stats for one series. `prices` must be date-indexed and sorted."""
    prices = prices.dropna()
    if prices.empty:
        return {}
    last_date = prices.index[-1]
    last = float(prices.iloc[-1])
    prev = float(prices.iloc[-2]) if len(prices) > 1 else None
    year_ago = prices[prices.index > last_date - pd.Timedelta(days=365)]
    ytd_base = prices[prices.index < pd.Timestamp(year=last_date.year, month=1, day=1)]

    def pct(a: float, b: float | None) -> float | None:
        return None if b in (None, 0) else (a / b - 1) * 100

    ma20 = prices.rolling(20).mean().iloc[-1] if len(prices) >= 20 else np.nan
    ma50 = prices.rolling(50).mean().iloc[-1] if len(prices) >= 50 else np.nan
    return {
        "last_date": last_date.date(),
        "last": last,
        "change": None if prev is None else last - prev,
        "change_pct": pct(last, prev),
        "ma20": None if np.isnan(ma20) else float(ma20),
        "ma50": None if np.isnan(ma50) else float(ma50),
        "vol_20d_annualized": annualized_volatility(prices, 20),
        "high_52w": float(year_ago.max()),
        "low_52w": float(year_ago.min()),
        "ytd_pct": pct(last, float(ytd_base.iloc[-1]) if not ytd_base.empty else None),
    }


def brent_wti_spread(frame: pd.DataFrame) -> pd.Series:
    both = frame[["brent", "wti"]].dropna()
    return (both["brent"] - both["wti"]).rename("brent_wti")


def crack_321(frame: pd.DataFrame) -> pd.Series:
    """3-2-1 crack in $/bbl: (2 bbl gasoline + 1 bbl distillate − 3 bbl crude) / 3."""
    f = frame[["rbob_nyh", "ulsd_nyh", "wti"]].dropna()
    gross = 2 * f["rbob_nyh"] * BARRELS_PER_GALLON + f["ulsd_nyh"] * BARRELS_PER_GALLON
    return ((gross - 3 * f["wti"]) / 3).rename("crack_321")


SPREAD_INPUTS: dict[str, tuple[list[str], Callable[[pd.DataFrame], pd.Series]]] = {
    "brent_wti": (["brent", "wti"], brent_wti_spread),
    "crack_321": (["rbob_nyh", "ulsd_nyh", "wti"], crack_321),
}


def with_zscore(spread: pd.Series, window: int = 60) -> pd.DataFrame:
    """Rolling mean and z-score: how stretched the spread is versus its recent range."""
    mean = spread.rolling(window, min_periods=window).mean()
    std = spread.rolling(window, min_periods=window).std(ddof=1)
    z = (spread - mean) / std.replace(0, np.nan)
    return pd.DataFrame({"value": spread, "mean": mean, "zscore": z})
