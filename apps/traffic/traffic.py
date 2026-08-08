"""Local traffic incidents via the 511.org Traffic Events API (Open511).

`events(lat, lon, radius_km)` returns active incidents/construction near a point,
most-relevant first (worse + closer wins). Road names are shortened to friendly
labels (CA-82 → EL CAMINO, US-101 → 101) and a compact summary is built from the
event's roads, since 511's own `headline` is a paragraph.

Reuses the same free 511 key as the transit app (TRANSIT_API_KEY /
FIVEONEONE_API_KEY). Cached ~5 min — incidents change slowly and the key is capped
at 60 requests/hour. No key → empty (the panel shows a hint).
"""
from __future__ import annotations

import json
import os
import time
from math import asin, cos, radians, sin, sqrt

import httpx

EVENTS_URL = "http://api.511.org/traffic/events"

# Freeway/route code → short human label that fits the panel.
_ROAD_LABEL = {
    "CA-82": "EL CAMINO",
    "US-101": "101",
    "I-280": "280",
    "CA-92": "92",
    "CA-1": "HWY 1",
    "CA-84": "84",
    "I-380": "380",
    "CA-35": "SKYLINE",
}

# Open511 severity → sort rank (higher = worse) so the worst float to the top.
_SEV_RANK = {"SEVERE": 4, "MAJOR": 3, "MODERATE": 2, "MINOR": 1, "UNKNOWN": 0}


def _api_key() -> str:
    return (os.environ.get("TRANSIT_API_KEY") or os.environ.get("FIVEONEONE_API_KEY") or "").strip()


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    h = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _first_coord(geography: dict):
    """Return (lat, lon) from a Point or the first vertex of a LineString."""
    if not isinstance(geography, dict):
        return None
    co = geography.get("coordinates")
    gtype = geography.get("type")
    try:
        if gtype == "Point":
            return float(co[1]), float(co[0])
        if gtype in ("LineString", "MultiPoint") and co:
            return float(co[0][1]), float(co[0][0])
    except (TypeError, ValueError, IndexError):
        return None
    return None


def _road_base(name: str) -> str:
    # names look like "CA-82 S" / "US-101 N" — the base code is the first token.
    parts = (name or "").split()
    return parts[0] if parts else ""


def _road_label(name: str) -> str:
    parts = (name or "").split()
    base = parts[0] if parts else ""
    direction = parts[1] if len(parts) > 1 else ""
    label = _ROAD_LABEL.get(base, base)
    return f"{label} {direction}".strip()


class TrafficClient:
    def __init__(self, timeout: float = 10.0, ttl: float = 300.0):
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "pi-led/0.1"}
        )
        self._cache: tuple[float, list[dict]] | None = None
        self._ttl = ttl  # 5 min — incidents change slowly; protects the 60/hr budget

    @property
    def has_key(self) -> bool:
        return bool(_api_key())

    async def close(self) -> None:
        await self._client.aclose()

    def _shape(
        self,
        raw: list[dict],
        lat: float,
        lon: float,
        radius_km: float,
        roads: list[str] | None,
        sort: str,
    ) -> list[dict]:
        want = {r.upper() for r in roads} if roads else None
        out: list[dict] = []
        for e in raw:
            if str(e.get("status", "")).upper() not in ("", "ACTIVE"):
                continue
            here = _first_coord(e.get("geography") or {})
            dist = _haversine_km(lat, lon, here[0], here[1]) if here else 999.0
            if dist > radius_km:
                continue
            road_list = e.get("roads") or []
            road0 = road_list[0] if road_list else {}
            code = _road_base(str(road0.get("name", "")))
            if want is not None and code.upper() not in want:
                continue
            etype = str(e.get("event_type", "")).upper()
            subtype = (e.get("event_subtypes") or [""])[0]
            frm = str(road0.get("from", "")).strip()
            to = str(road0.get("to", "")).strip()
            where = f"{frm}-{to}" if frm and to else (frm or to)
            out.append(
                {
                    "road": _road_label(str(road0.get("name", ""))),
                    "code": code,
                    "type": etype,
                    "subtype": subtype,
                    "severity": str(e.get("severity", "Unknown")),
                    "where": where,
                    "dist_km": round(dist, 1),
                    "area": (e.get("areas") or [{}])[0].get("name", ""),
                }
            )
        if sort == "distance":
            out.sort(key=lambda d: d["dist_km"])
        else:  # "severity": worst first, then nearest
            out.sort(key=lambda d: (-_SEV_RANK.get(d["severity"].upper(), 0), d["dist_km"]))
        return out

    async def _raw(self) -> list[dict]:
        key = _api_key()
        if not key:
            return []
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self._ttl:
            return self._cache[1]
        try:
            r = await self._client.get(EVENTS_URL, params={"api_key": key, "format": "json"})
            r.raise_for_status()
            data = json.loads(r.content.decode("utf-8-sig", errors="replace"))
            raw = data.get("events", []) or []
            self._cache = (now, raw)
            return raw
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return self._cache[1] if self._cache else []

    async def events(
        self,
        lat: float,
        lon: float,
        radius_km: float = 6.0,
        roads: list[str] | None = None,
        sort: str = "severity",
    ) -> list[dict]:
        """Incidents within radius_km of (lat, lon). `roads` filters to specific
        base codes (e.g. ['US-101','I-280']); `sort` is 'severity' or 'distance'."""
        if not _api_key():
            return []
        return self._shape(await self._raw(), lat, lon, radius_km, roads, sort)
