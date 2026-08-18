"""SFO (or any airport) flight board via the AeroDataBox API (RapidAPI).

`board(icao, hours)` returns the upcoming departures and arrivals as two lists of
small dicts (flight number, airline, the other city, local time, minutes-until,
status, delay, terminal/gate, region tier). Flights already in the past (by
scheduled/revised time) are dropped here. Each flight is tagged with a `tier`
(see regions.py: Europe/India > other international > domestic) and each list is
sorted tier-first, then soonest-first, so the higher tiers are what survive the
per-section trim in plugin.py. One call returns the whole board; callers filter
for the display, so filtering costs no extra API budget.

Needs a free RapidAPI key subscribed to AeroDataBox (Basic, ~600 units/month, no
credit card), read from AERODATABOX_API_KEY / RAPIDAPI_KEY. Cached with a long TTL
(the board doesn't churn minute-to-minute and the budget is tight). No key →
empty (the panel shows a hint).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from .regions import tier as _region_tier

_HOST = "aerodatabox.p.rapidapi.com"
_URL = "https://aerodatabox.p.rapidapi.com/flights/airports/icao/{icao}/{start}/{end}"
_TZ = ZoneInfo("America/Los_Angeles")  # SFO local; used to build the query window


def _api_key() -> str:
    return (os.environ.get("AERODATABOX_API_KEY") or os.environ.get("RAPIDAPI_KEY") or "").strip()


def _parse_utc(node: dict | None) -> datetime | None:
    """AeroDataBox time node: {'utc': '2026-08-08 21:00Z', 'local': '...'} -> dt."""
    if not isinstance(node, dict):
        return None
    raw = node.get("utc") or ""
    try:
        return datetime.fromisoformat(raw.replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None


def _local_hhmm(node: dict | None) -> str:
    """The wall-clock HH:MM from a time node's local string, e.g. '14:45'."""
    if not isinstance(node, dict):
        return ""
    raw = str(node.get("local") or "")
    # "2026-08-08 14:45-07:00" -> take the time token
    parts = raw.replace("T", " ").split(" ")
    if len(parts) >= 2 and ":" in parts[1]:
        return parts[1][:5]
    return ""


class FlightsClient:
    def __init__(self, timeout: float = 12.0, ttl: float = 1800.0):
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._ttl = ttl  # 30 min — protects the ~600 units/month AeroDataBox budget

    @property
    def has_key(self) -> bool:
        return bool(_api_key())

    async def close(self) -> None:
        await self._client.aclose()

    def _shape(self, flights: list, kind: str, now: datetime) -> list[dict]:
        out: list[dict] = []
        for f in flights or []:
            mv = f.get("movement") or {}
            sched = _parse_utc(mv.get("scheduledTime"))
            revised = _parse_utc(mv.get("revisedTime"))
            when = revised or sched
            if when is None or when < now:  # drop flights already in the past
                continue
            delay_min = int(round((revised - sched).total_seconds() / 60)) if (revised and sched) else 0
            ap = mv.get("airport") or {}
            iata = str(ap.get("iata") or "").strip()
            out.append(
                {
                    "number": str(f.get("number") or "").strip(),
                    "airline": str((f.get("airline") or {}).get("name") or "").strip(),
                    "city": str(ap.get("name") or "").strip(),
                    "iata": iata,
                    "time": _local_hhmm(mv.get("scheduledTime")),
                    "minutes": int(round((when - now).total_seconds() / 60)),
                    "when_ts": when.timestamp(),  # re-checked in plugin.py against cache staleness
                    "status": str(f.get("status") or "").strip(),
                    "delay_min": delay_min,
                    "terminal": str(mv.get("terminal") or "").strip(),
                    "gate": str(mv.get("gate") or "").strip(),
                    "kind": kind,
                    "tier": _region_tier(iata),
                }
            )
        out.sort(key=lambda d: (-d["tier"], d["minutes"]))
        return out

    async def board(self, icao: str = "KSFO", hours: int = 8) -> dict:
        """{'departures': [...], 'arrivals': [...]} upcoming, soonest first."""
        key = _api_key()
        if not key:
            return {"departures": [], "arrivals": []}
        now_local = datetime.now(_TZ)
        # AeroDataBox caps the window at 12h; query from ~now to now+hours.
        start = now_local.strftime("%Y-%m-%dT%H:%M")
        end = (now_local + timedelta(hours=min(hours, 12))).strftime("%Y-%m-%dT%H:%M")
        ck = f"{icao}:{start}"
        mono = time.monotonic()
        hit = self._cache.get(ck)
        if hit and mono - hit[0] < self._ttl:
            return hit[1]
        url = _URL.format(icao=icao, start=start, end=end)
        params = {
            "direction": "Both",
            "withLeg": "false",
            "withCancelled": "true",
            "withCodeshared": "false",
            "withCargo": "false",
            "withPrivate": "false",
            "withLocation": "false",
        }
        headers = {"x-rapidapi-key": key, "x-rapidapi-host": _HOST}
        try:
            r = await self._client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
            now_utc = datetime.now(timezone.utc)
            board = {
                "departures": self._shape(data.get("departures"), "DEP", now_utc),
                "arrivals": self._shape(data.get("arrivals"), "ARR", now_utc),
            }
            self._cache[ck] = (mono, board)
            return board
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else {"departures": [], "arrivals": []}
