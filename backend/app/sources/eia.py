"""Client for the U.S. Energy Information Administration (EIA) Open Data API v2.

Docs: https://www.eia.gov/opendata/documentation.php
"""

from __future__ import annotations

import logging
import time
from datetime import date

import httpx

from app.catalog import SeriesDef
from app.sources import Observation

log = logging.getLogger(__name__)

BASE_URL = "https://api.eia.gov/v2"
PAGE_SIZE = 5000  # EIA's maximum rows per request


class EIAError(RuntimeError):
    pass


class EIAClient:
    name = "eia"

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        if not api_key:
            raise ValueError("EIA_API_KEY is required for the EIA source")
        self.api_key = api_key
        self.client = client or httpx.Client(base_url=BASE_URL, timeout=30.0)
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def _get(self, path: str, params: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.get(path, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise EIAError(f"EIA returned HTTP {resp.status_code}")
                resp.raise_for_status()
                payload = resp.json()
                if "error" in payload:
                    raise EIAError(str(payload["error"]))
                return payload
            except (httpx.TransportError, EIAError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = self.backoff_seconds * 2 ** (attempt - 1)
                    log.warning("EIA request failed (%s); retry %d in %.1fs", exc, attempt, wait)
                    time.sleep(wait)
        raise EIAError(f"EIA request failed after {self.max_retries} attempts: {last_exc}")

    def fetch(self, series: SeriesDef, start: date, end: date | None = None) -> list[Observation]:
        params: dict[str, str | int] = {
            "api_key": self.api_key,
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": series.eia_series,
            "start": start.isoformat(),
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": PAGE_SIZE,
        }
        if end:
            params["end"] = end.isoformat()

        rows: list[Observation] = []
        offset = 0
        while True:
            params["offset"] = offset
            payload = self._get(f"/{series.eia_route}/data/", params)
            body = payload.get("response", {})
            page = body.get("data", [])
            for item in page:
                value = item.get("value")
                if value in (None, "", "NA"):
                    continue  # EIA leaves holidays/missing prints blank
                rows.append(
                    Observation(series.id, date.fromisoformat(item["period"]), float(value))
                )
            total = int(body.get("total", 0) or 0)
            offset += len(page)
            if not page or offset >= total:
                break
        return rows
