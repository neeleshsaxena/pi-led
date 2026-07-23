"""Recent-rain lookup for the plant reminder (Open-Meteo, free, no API key).

`last_rain_date(place)` returns the most recent local date with at least
`threshold_mm` of precipitation over the past ~10 days (including today), so
outdoor plants can treat rain as a watering. Geocode + result are cached to keep
the render loop cheap; on any network error it serves the last good value.
"""
from __future__ import annotations

import time
from datetime import date

import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class RainClient:
    def __init__(self, timeout: float = 8.0):
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "pi-led/0.1"})
        self._geo: dict[str, tuple[float, float]] = {}
        self._cache: dict[str, tuple[float, date | None]] = {}  # place -> (mono_ts, last_rain)
        self._ttl = 1800.0  # 30 min — rain history doesn't change fast

    async def close(self) -> None:
        await self._client.aclose()

    async def _geocode(self, place: str) -> tuple[float, float]:
        if place in self._geo:
            return self._geo[place]
        r = await self._client.get(
            GEO_URL, params={"name": place, "count": 1, "language": "en", "format": "json"}
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            raise ValueError(f"no geocode for {place!r}")
        latlon = (results[0]["latitude"], results[0]["longitude"])
        self._geo[place] = latlon
        return latlon

    async def last_rain_date(self, place: str, threshold_mm: float = 1.0) -> date | None:
        """Most recent day it rained >= threshold_mm at `place` (or None)."""
        now = time.monotonic()
        hit = self._cache.get(place)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        try:
            lat, lon = await self._geocode(place)
            r = await self._client.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "precipitation_sum",
                    "past_days": 10,
                    "forecast_days": 1,
                    "timezone": "auto",
                },
            )
            r.raise_for_status()
            daily = r.json().get("daily") or {}
            times = daily.get("time") or []
            sums = daily.get("precipitation_sum") or []
            last: date | None = None
            for t, s in zip(times, sums):  # chronological → last match is most recent
                if s is not None and s >= threshold_mm:
                    last = date.fromisoformat(t)
            self._cache[place] = (now, last)
            return last
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else None
