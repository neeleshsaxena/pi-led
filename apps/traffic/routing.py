"""Live traffic-aware travel time via the TomTom Routing API.

`eta(origin, dest)` returns the current driving time with live traffic, the
free-flow time, and the delay between them — enough to show "34 min, +8 in
traffic" and colour it by how congested the drive is.

Needs a free TomTom key (developer.tomtom.com — 2,500 requests/day, no credit
card), read from TOMTOM_API_KEY / ROUTING_API_KEY. No key → None (panel shows a
hint). Cached ~3 min: one commute route is well inside the daily budget and the
render loop must not fetch every frame.
"""
from __future__ import annotations

import json
import os
import time

import httpx

ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute/{o_lat},{o_lon}:{d_lat},{d_lon}/json"


def _api_key() -> str:
    return (os.environ.get("TOMTOM_API_KEY") or os.environ.get("ROUTING_API_KEY") or "").strip()


class RoutingClient:
    def __init__(self, timeout: float = 10.0, ttl: float = 180.0):
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "pi-led/0.1"}
        )
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._ttl = ttl

    @property
    def has_key(self) -> bool:
        return bool(_api_key())

    async def close(self) -> None:
        await self._client.aclose()

    async def eta(self, o_lat: float, o_lon: float, d_lat: float, d_lon: float) -> dict | None:
        """{'minutes','free_min','delay_min','km'} for the drive, or None."""
        key = _api_key()
        if not key:
            return None
        ck = (round(o_lat, 4), round(o_lon, 4), round(d_lat, 4), round(d_lon, 4))
        now = time.monotonic()
        hit = self._cache.get(ck)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        url = ROUTE_URL.format(o_lat=o_lat, o_lon=o_lon, d_lat=d_lat, d_lon=d_lon)
        params = {
            "key": key,
            "traffic": "true",
            "computeTravelTimeFor": "all",
            "travelMode": "car",
        }
        try:
            r = await self._client.get(url, params=params)
            r.raise_for_status()
            data = json.loads(r.content.decode("utf-8-sig", errors="replace"))
            summ = (data.get("routes") or [{}])[0].get("summary") or {}
            travel = summ.get("travelTimeInSeconds")
            if travel is None:
                return hit[1] if hit else None
            free = summ.get("noTrafficTravelTimeInSeconds", travel)
            delay = summ.get("trafficDelayInSeconds", 0) or 0
            out = {
                "minutes": int(round(travel / 60.0)),
                "free_min": int(round(free / 60.0)),
                "delay_min": int(round(delay / 60.0)),
                "km": round(summ.get("lengthInMeters", 0) / 1000.0, 1),
            }
            self._cache[ck] = (now, out)
            return out
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else None
