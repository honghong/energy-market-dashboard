from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.catalog import SERIES_BY_ID
from app.sources.eia import BASE_URL, EIAClient, EIAError


def _page(rows: list[tuple[str, str | None]], total: int) -> dict:
    return {
        "response": {
            "total": str(total),
            "data": [
                {"period": p, "series": "RWTC", "value": v, "units": "$/BBL"} for p, v in rows
            ],
        }
    }


def make_client(handler) -> EIAClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url=BASE_URL, transport=transport)
    return EIAClient("test-key", client=http, backoff_seconds=0)


def test_fetch_parses_rows_and_skips_blanks():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=_page([("2026-10-14", "71.25"), ("2026-10-15", None), ("2026-10-16", "70.10")], 3),
        )

    rows = make_client(handler).fetch(SERIES_BY_ID["wti"], date(2026, 10, 1))

    assert [(r.period, r.value) for r in rows] == [
        (date(2026, 10, 14), 71.25),
        (date(2026, 10, 16), 70.10),
    ]
    params = seen[0].url.params
    assert seen[0].url.path == "/v2/petroleum/pri/spt/data/"
    assert params["facets[series][]"] == "RWTC"
    assert params["start"] == "2026-10-01"
    assert params["api_key"] == "test-key"


def test_fetch_follows_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        if offset == 0:
            return httpx.Response(200, json=_page([("2026-01-02", "60"), ("2026-01-05", "61")], 3))
        return httpx.Response(200, json=_page([("2026-01-06", "62")], 3))

    rows = make_client(handler).fetch(SERIES_BY_ID["wti"], date(2026, 1, 1))
    assert [r.value for r in rows] == [60.0, 61.0, 62.0]


def test_retries_transient_errors_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_page([("2026-01-02", "60")], 1))

    rows = make_client(handler).fetch(SERIES_BY_ID["wti"], date(2026, 1, 1))
    assert calls["n"] == 3
    assert len(rows) == 1


def test_gives_up_after_max_retries():
    client = make_client(lambda request: httpx.Response(500))
    with pytest.raises(EIAError):
        client.fetch(SERIES_BY_ID["wti"], date(2026, 1, 1))


def test_api_error_payload_raises():
    client = make_client(lambda request: httpx.Response(200, json={"error": "invalid api_key"}))
    with pytest.raises(EIAError, match="invalid api_key"):
        client.fetch(SERIES_BY_ID["wti"], date(2026, 1, 1))


def test_requires_api_key():
    with pytest.raises(ValueError):
        EIAClient("")
