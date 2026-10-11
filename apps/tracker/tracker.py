"""Track a specific flight by number via AeroDataBox (RapidAPI).

`status(number, date, ttl)` returns a normalized status dict for one flight on a
given local date, or None. This is the *flight-by-number* endpoint (≈2 AeroDataBox
units/call) — distinct from the airport-board endpoint the `flights` app uses.

Budget-safe by construction, because the budget is shared with `flights` (free
Basic = 600 units/month):
  - results are cached per (number, date) with a caller-chosen TTL (the plugin
    polls coarsely far from events, finely near a departure/landing, and only
    inside the trip's active window — so no calls at all on the days around it);
  - a hard **calls-per-day cap** is a backstop against any logic bug; and
  - calls are spaced ≥`min_spacing`s apart to respect the plan's per-second rate
    limit (bursting returns 429).

Reuses AERODATABOX_API_KEY / RAPIDAPI_KEY. No key → None (panel shows a hint).
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone

import httpx

_HOST = "aerodatabox.p.rapidapi.com"
_URL = "https://aerodatabox.p.rapidapi.com/flights/number/{number}/{date}"


def _api_key() -> str:
    return (os.environ.get("AERODATABOX_API_KEY") or os.environ.get("RAPIDAPI_KEY") or "").strip()


def _dt(node: dict | None, field: str) -> datetime | None:
    """Parse a time node's UTC instant, e.g. {'utc': '2026-10-06 02:00Z'}."""
    if not isinstance(node, dict):
        return None
    raw = (node.get(field) or {}).get("utc") if isinstance(node.get(field), dict) else ""
    try:
        return datetime.fromisoformat(str(raw).replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None


def _hhmm(node: dict | None, field: str) -> str:
    """The wall-clock HH:MM from a time node's local string ('... 14:10-07:00')."""
    if not isinstance(node, dict) or not isinstance(node.get(field), dict):
        return ""
    raw = str(node[field].get("local") or "")
    parts = raw.replace("T", " ").split(" ")
    return parts[1][:5] if len(parts) >= 2 and ":" in parts[1] else ""


class TrackerClient:
    def __init__(self, timeout: float = 15.0, max_calls_per_day: int = 48,
                 min_spacing: float = 1.5):
        self._client = httpx.AsyncClient(timeout=timeout)
        self._cache: dict[tuple[str, str], tuple[float, dict]] = {}
        self._max_per_day = max_calls_per_day
        self._day: str = ""
        self._calls_today = 0
        self._last_call = float("-inf")   # monotonic of the last network call
        self._min_spacing = min_spacing

    @property
    def has_key(self) -> bool:
        return bool(_api_key())

    async def close(self) -> None:
        await self._client.aclose()

    def _rollover(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._day:
            self._day, self._calls_today = today, 0

    async def status(self, number: str, date: str, ttl: float) -> dict | None:
        """Cached live status for `number` on local `date` (YYYY-MM-DD). The caller
        owns the polling cadence via `ttl` + by only calling inside the window."""
        key = _api_key()
        if not key or not number or not date:
            return None
        ck = (number.upper(), date)
        mono = time.monotonic()
        hit = self._cache.get(ck)
        if hit and mono - hit[0] < ttl:
            return hit[1]
        self._rollover()
        if self._calls_today >= self._max_per_day:   # budget backstop
            return hit[1] if hit else None
        gap = mono - self._last_call                  # per-second rate-limit spacing
        if gap < self._min_spacing:
            await asyncio.sleep(self._min_spacing - gap)
        self._last_call = time.monotonic()
        self._calls_today += 1
        try:
            r = await self._client.get(
                _URL.format(number=number.upper(), date=date),
                headers={"x-rapidapi-key": key, "x-rapidapi-host": _HOST},
                params={"withAircraftImage": "false", "withLocation": "false"},
            )
            r.raise_for_status()
            payload = r.json()
            flights = payload if isinstance(payload, list) else payload.get("flights", [])
            data = self._shape(number.upper(), flights)
            self._cache[ck] = (mono, data)
            return data
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else None

    @staticmethod
    def _shape(number: str, flights: list) -> dict:
        f = (flights or [{}])[0]
        out = {"number": number, "status": str(f.get("status") or "")}
        for role, node in (("dep", f.get("departure") or {}), ("arr", f.get("arrival") or {})):
            ap = node.get("airport") or {}
            sched = _dt(node, "scheduledTime")
            # revised/predicted/actual, whichever the feed has, is the live estimate
            live_field = next((x for x in ("actualTime", "revisedTime", "predictedTime")
                               if isinstance(node.get(x), dict)), "scheduledTime")
            est = _dt(node, live_field)
            delay = int(round((est - sched).total_seconds() / 60)) if (est and sched) else 0
            out[role] = {
                "iata": str(ap.get("iata") or ""),
                "sched_hhmm": _hhmm(node, "scheduledTime"),
                "est_hhmm": _hhmm(node, live_field),
                "sched_utc": sched,
                "est_utc": est or sched,
                "delay_min": delay,
                "terminal": str(node.get("terminal") or ""),
                "gate": str(node.get("gate") or ""),
            }
        return out
