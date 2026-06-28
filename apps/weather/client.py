"""Open-Meteo weather client for the weather LED app. Free, no API key.

Self-contained (same spirit as the worldcup ESPN client). Geocodes a place name
to lat/lon, then fetches current conditions + a few days of forecast, cached
with a TTL. WMO weather codes are mapped to a small set of icon keys the
renderer knows how to draw.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code -> (short label, icon key). icon keys the renderer draws:
# clear, partly, cloud, fog, rain, snow, storm.
_WMO: dict[int, tuple[str, str]] = {
    0: ("CLEAR", "clear"),
    1: ("CLEAR", "clear"), 2: ("PARTLY", "partly"), 3: ("CLOUDY", "cloud"),
    45: ("FOG", "fog"), 48: ("FOG", "fog"),
    51: ("DRIZZLE", "rain"), 53: ("DRIZZLE", "rain"), 55: ("DRIZZLE", "rain"),
    56: ("ICE", "rain"), 57: ("ICE", "rain"),
    61: ("RAIN", "rain"), 63: ("RAIN", "rain"), 65: ("RAIN", "rain"),
    66: ("ICE RAIN", "rain"), 67: ("ICE RAIN", "rain"),
    71: ("SNOW", "snow"), 73: ("SNOW", "snow"), 75: ("SNOW", "snow"), 77: ("SNOW", "snow"),
    80: ("SHOWERS", "rain"), 81: ("SHOWERS", "rain"), 82: ("SHOWERS", "rain"),
    85: ("SNOW", "snow"), 86: ("SNOW", "snow"),
    95: ("STORM", "storm"), 96: ("STORM", "storm"), 99: ("STORM", "storm"),
}


def describe(code: int) -> tuple[str, str]:
    return _WMO.get(int(code), ("—", "cloud"))


@dataclass
class Current:
    temp: float
    code: int
    high: float
    low: float
    humidity: int
    wind: float
    is_day: bool

    @property
    def label(self) -> str:
        return describe(self.code)[0]

    @property
    def icon(self) -> str:
        return describe(self.code)[1]


@dataclass
class Day:
    dow: str
    code: int
    high: float
    low: float

    @property
    def icon(self) -> str:
        return describe(self.code)[1]


@dataclass
class WeatherSnapshot:
    place: str
    current: Current
    days: list[Day] = field(default_factory=list)
    unit: str = "fahrenheit"
    stale: bool = False


class WeatherClient:
    def __init__(self, timeout: float = 8.0):
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "pi-led/0.1"})
        self._cache: dict[tuple, WeatherSnapshot] = {}
        self._cache_ts: dict[tuple, float] = {}
        self._geo: dict[str, tuple[float, float, str]] = {}
        self._ttl = 600.0  # 10 min

    async def close(self) -> None:
        await self._client.aclose()

    async def _geocode(self, place: str) -> tuple[float, float, str]:
        if place in self._geo:
            return self._geo[place]
        r = await self._client.get(GEO_URL, params={"name": place, "count": 1})
        r.raise_for_status()
        results = (r.json().get("results") or [])
        if not results:
            raise ValueError(f"place not found: {place!r}")
        g = results[0]
        out = (g["latitude"], g["longitude"], g.get("name") or place)
        self._geo[place] = out
        return out

    async def get(self, place: str = "San Francisco", unit: str = "fahrenheit", force: bool = False) -> WeatherSnapshot:
        key = (place, unit)
        now = time.monotonic()
        if not force and key in self._cache and (now - self._cache_ts[key]) < self._ttl:
            return self._cache[key]
        try:
            lat, lon, name = await self._geocode(place)
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "temperature_unit": unit,
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 4,
            }
            r = await self._client.get(FORECAST_URL, params=params)
            r.raise_for_status()
            data = r.json()
        except Exception:
            if key in self._cache:
                self._cache[key].stale = True
                return self._cache[key]
            raise

        cur = data.get("current", {}) or {}
        daily = data.get("daily", {}) or {}
        highs = daily.get("temperature_2m_max", []) or []
        lows = daily.get("temperature_2m_min", []) or []
        codes = daily.get("weather_code", []) or []
        dates = daily.get("time", []) or []

        days: list[Day] = []
        for i in range(min(len(dates), 4)):
            try:
                dow = datetime.fromisoformat(dates[i]).strftime("%a").upper()
            except ValueError:
                dow = "—"
            days.append(Day(
                dow=dow,
                code=int(codes[i]) if i < len(codes) else 0,
                high=highs[i] if i < len(highs) else 0,
                low=lows[i] if i < len(lows) else 0,
            ))

        current = Current(
            temp=cur.get("temperature_2m", 0),
            code=int(cur.get("weather_code", 0)),
            high=highs[0] if highs else cur.get("temperature_2m", 0),
            low=lows[0] if lows else cur.get("temperature_2m", 0),
            humidity=int(cur.get("relative_humidity_2m", 0)),
            wind=cur.get("wind_speed_10m", 0),
            is_day=bool(cur.get("is_day", 1)),
        )
        snap = WeatherSnapshot(place=name, current=current, days=days, unit=unit)
        self._cache[key] = snap
        self._cache_ts[key] = now
        return snap
