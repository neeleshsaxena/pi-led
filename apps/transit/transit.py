"""Bay Area real-time transit departures via the 511.org SIRI API.

`departures(agency, stopcode)` returns the upcoming departures at a stop as a list
of small dicts (line, destination, direction, the absolute expected/aimed times).
Works for any 511 operator — Caltrain (agency "CT"), SamTrans buses ("SM"), etc.

Two deliberate choices keep us inside 511's tight budget (60 requests/hour/key):
  - results are cached per stop with a ~2 min TTL, and
  - we return *absolute* departure timestamps, so the render loop can recompute the
    "minutes until" countdown every frame without re-fetching — the countdown stays
    second-accurate between fetches; only delay revisions wait for the next refresh.

Needs a free key (511.org/open-data/token), read from TRANSIT_API_KEY /
FIVEONEONE_API_KEY, or passed in. No key → empty result (the panel shows a hint).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone

import httpx

STOP_MON_URL = "http://api.511.org/transit/StopMonitoring"


def _api_key() -> str:
    return (os.environ.get("TRANSIT_API_KEY") or os.environ.get("FIVEONEONE_API_KEY") or "").strip()


def _parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # 511 emits ISO-8601 UTC, e.g. "2026-08-07T15:42:00Z".
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _clean_dest(name: str) -> str:
    """Destinations arrive verbose — Caltrain 'San Francisco Caltrain Station
    Northbound', bus 'Mission St & 1st St (Northbound)'. Trim the boilerplate."""
    s = " ".join((name or "").split())
    s = re.sub(r"\s*\([^)]*\)", "", s)  # drop "(Northbound)" etc.
    for junk in (" Caltrain Station", " Caltrain", " Station", " Northbound", " Southbound"):
        s = s.replace(junk, "")
    return s.strip()


class TransitClient:
    def __init__(self, timeout: float = 8.0, ttl: float = 120.0):
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "pi-led/0.1"}
        )
        self._cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
        self._ttl = ttl  # 60 req/hour/key budget → refresh a stop at most ~2 min

    @property
    def has_key(self) -> bool:
        return bool(_api_key())

    async def close(self) -> None:
        await self._client.aclose()

    def _parse(self, payload: str) -> list[dict]:
        # 511 JSON is served with a UTF-8 BOM; utf-8-sig on the caller strips it,
        # but guard here too in case a raw string slips through.
        try:
            data = json.loads(payload.lstrip("﻿"))
        except (json.JSONDecodeError, ValueError):
            return []
        delivery = (data.get("ServiceDelivery") or {}).get("StopMonitoringDelivery") or {}
        # StopMonitoringDelivery is usually an object, occasionally a 1-element list.
        if isinstance(delivery, list):
            delivery = delivery[0] if delivery else {}
        out: list[dict] = []
        for visit in _as_list(delivery.get("MonitoredStopVisit")):
            j = visit.get("MonitoredVehicleJourney") or {}
            call = j.get("MonitoredCall") or {}
            aimed = _parse_time(call.get("AimedDepartureTime") or call.get("AimedArrivalTime"))
            expected = _parse_time(
                call.get("ExpectedDepartureTime")
                or call.get("ExpectedArrivalTime")
                or call.get("AimedDepartureTime")
                or call.get("AimedArrivalTime")
            )
            if expected is None:
                continue
            framed = j.get("FramedVehicleJourneyRef") or {}
            train = str(framed.get("DatedVehicleJourneyRef") or j.get("VehicleRef") or "").strip()
            out.append(
                {
                    # LineRef is the short code (bus "ECR"/"292", Caltrain service
                    # name "Local Weekend"); prefer it over the verbose display name.
                    "line": str(j.get("LineRef") or j.get("PublishedLineName") or "").strip(),
                    "train": train,  # Caltrain train #, e.g. "631"
                    "dest": _clean_dest(str(j.get("DestinationName") or "")),
                    "direction": str(j.get("DirectionRef") or "").strip().upper(),
                    "expected": expected,
                    "aimed": aimed,
                    "delayed": bool(aimed and expected and (expected - aimed).total_seconds() > 90),
                }
            )
        out.sort(key=lambda d: d["expected"])
        return out

    async def departures(self, agency: str, stopcode: str) -> list[dict]:
        """Upcoming departures at (agency, stopcode), soonest first. Cached ~2 min."""
        key = _api_key()
        if not key:
            return []
        ck = (agency, str(stopcode))
        now = time.monotonic()
        hit = self._cache.get(ck)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        params = {"api_key": key, "agency": agency, "stopcode": str(stopcode), "format": "json"}
        try:
            r = await self._client.get(STOP_MON_URL, params=params)
            r.raise_for_status()
            items = self._parse(r.content.decode("utf-8-sig", errors="replace"))
            self._cache[ck] = (now, items)
            return items
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else []


def minutes_until(dt: datetime, now: datetime | None = None) -> int:
    """Whole minutes from now until dt (may be negative if it just departed)."""
    now = now or datetime.now(timezone.utc)
    return int(round((dt - now).total_seconds() / 60.0))
