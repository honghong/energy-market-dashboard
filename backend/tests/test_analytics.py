from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app import analytics


def series(values: list[float], start: str = "2026-01-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_moving_averages_need_a_full_window():
    out = analytics.with_moving_averages(series([1, 2, 3, 4, 5]), windows=(3,))
    assert out["ma3"].isna().tolist() == [True, True, False, False, False]
    assert out["ma3"].iloc[-1] == pytest.approx(4.0)


def test_volatility_of_constant_growth_is_zero():
    prices = series([100 * 1.01**i for i in range(30)])
    assert analytics.annualized_volatility(prices, 20) == pytest.approx(0.0, abs=1e-12)


def test_volatility_matches_manual_formula():
    rng = np.random.default_rng(0)
    prices = series(list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 60)))))
    expected = np.log(prices).diff().dropna().iloc[-20:].std(ddof=1) * np.sqrt(252)
    assert analytics.annualized_volatility(prices, 20) == pytest.approx(expected)


def test_volatility_none_when_history_too_short():
    assert analytics.annualized_volatility(series([1, 2, 3]), 20) is None


def test_summary_change_and_ytd():
    idx = pd.to_datetime(["2025-12-30", "2025-12-31", "2026-01-02", "2026-01-05"])
    prices = pd.Series([80.0, 80.0, 84.0, 88.0], index=idx)
    s = analytics.summarize(prices)
    assert s["last"] == 88.0
    assert s["change"] == pytest.approx(4.0)
    assert s["change_pct"] == pytest.approx(4 / 84 * 100)
    assert s["ytd_pct"] == pytest.approx(10.0)  # vs last 2025 close of 80
    assert s["high_52w"] == 88.0 and s["low_52w"] == 80.0
    assert s["ma20"] is None


def test_brent_wti_spread_aligns_on_common_dates():
    frame = pd.DataFrame(
        {"brent": [75.0, np.nan, 77.0], "wti": [71.0, 72.0, 72.5]},
        index=pd.bdate_range("2026-03-02", periods=3),
    )
    spread = analytics.brent_wti_spread(frame)
    assert spread.tolist() == [4.0, 4.5]


def test_crack_321_formula():
    # RBOB $2.50/gal = $105/bbl, ULSD $2.75/gal = $115.50/bbl, WTI $70.
    frame = pd.DataFrame(
        {"rbob_nyh": [2.50], "ulsd_nyh": [2.75], "wti": [70.0]},
        index=pd.bdate_range("2026-03-02", periods=1),
    )
    expected = (2 * 105.0 + 115.5 - 3 * 70.0) / 3
    assert analytics.crack_321(frame).iloc[0] == pytest.approx(expected)


def test_zscore_flags_a_stretched_spread():
    values = [4.0, 4.2, 3.8] * 20 + [8.0]
    out = analytics.with_zscore(series(values), window=60)
    assert out["zscore"].iloc[-1] > 3
    assert out["zscore"].iloc[:59].isna().all()
