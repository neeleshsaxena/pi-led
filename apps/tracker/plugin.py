"""Track one multi-leg flight journey on the panel (e.g. BOM→DXB→SFO).

Shows the whole itinerary with the live status of the leg that's currently in the
air (or next up), plus the final-destination arrival time + delay and a countdown
until the trip is over. Data/config/lifecycle here (lead-owned); pixel layout in
render.py (UI-owned).

Config: `label` (header, e.g. "SFO") and `legs` — an ordered list of
`{number, date, from, to, dep_local, arr_local, dep_utc, arr_utc}`. `dep_utc`/
`arr_utc` are the scheduled instants (ISO-8601), used to size the active window
and show times/countdowns with **zero** API calls outside the window; the rest
come from AeroDataBox only while a leg is actually in flight. Committed default is
empty (no trip) → the view hides itself; the real journey lives in stored config /
TRACKER_LEGS. Reuses the flights app's AeroDataBox key.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .render import render_tracker
from .tracker import TrackerClient

# Polling window per leg (relative to its scheduled times) + cadence.
POLL_LEAD = timedelta(hours=3)      # start polling this long before scheduled dep
POLL_TRAIL = timedelta(hours=3)     # keep polling this long after scheduled arr (late landings)
NEAR = timedelta(minutes=90)        # "near an event" => poll finely
TTL_NEAR = 20 * 60.0                # 20 min near a dep/arr
TTL_FAR = 60 * 60.0                 # 60 min otherwise
# Carousel visibility (no API cost outside the poll window above).
SHOW_LEAD = timedelta(days=2)       # appear in the carousel from 2 days out
SHOW_TRAIL = timedelta(hours=3)     # linger a few hours after arrival


def _iso(s) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _env_legs() -> list[dict] | None:
    raw = os.environ.get("TRACKER_LEGS", "").strip()
    if not raw:
        return None
    try:
        legs = json.loads(raw)
        return legs if isinstance(legs, list) and legs else None
    except (json.JSONDecodeError, ValueError):
        return None


def _done(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in ("arriv", "land", "cancel", "diverted"))


class TrackerApp(LedApp):
    id = "tracker"
    name = "Flight Tracker"

    def __init__(self) -> None:
        self.client: TrackerClient | None = None
        self._status: dict[str, dict] = {}   # number -> last-good status

    def default_config(self) -> dict:
        return {"label": os.environ.get("TRACKER_LABEL", ""), "legs": _env_legs() or []}

    def views(self) -> list[ViewSpec]:
        return [ViewSpec(id="main", label="Flight Tracker")]

    async def start(self) -> None:
        self.client = TrackerClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    def _legs(self, cfg: dict) -> list[dict]:
        legs = (cfg or {}).get("legs")
        return legs if isinstance(legs, list) else []

    def _span(self, legs: list[dict]) -> tuple[datetime | None, datetime | None]:
        deps = [d for d in (_iso(l.get("dep_utc")) for l in legs) if d]
        arrs = [a for a in (_iso(l.get("arr_utc")) for l in legs) if a]
        return (min(deps) if deps else None, max(arrs) if arrs else None)

    def _ttl_for(self, dep: datetime | None, arr: datetime | None, now: datetime) -> float:
        near = any(abs((now - t).total_seconds()) <= NEAR.total_seconds()
                   for t in (dep, arr) if t)
        return TTL_NEAR if near else TTL_FAR

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        legs = self._legs(cfg)
        now = datetime.now(timezone.utc)
        has_key = bool(self.client and self.client.has_key)

        for leg in legs:
            num = str(leg.get("number", "")).strip().upper()
            date = str(leg.get("date", "")).strip()
            dep, arr = _iso(leg.get("dep_utc")), _iso(leg.get("arr_utc"))
            if not (num and date and dep and arr):
                continue
            # Only hit the API inside this leg's active window, and not once it's done.
            in_window = (dep - POLL_LEAD) <= now <= (arr + POLL_TRAIL)
            if self.client is not None and in_window and not _done(self._status.get(num, {}).get("status", "")):
                fresh = await self.client.status(num, date, self._ttl_for(dep, arr, now))
                if fresh:
                    self._status[num] = fresh

        return render_tracker(
            label=str(cfg.get("label", "")),
            legs=legs,
            status=self._status,
            now=now,
            has_key=has_key,
            tick=ctx.tick,
        )

    def has_content(self, view_id: str, config: dict) -> bool:
        # Only occupy a carousel slot from a couple days before the trip through a
        # few hours after it lands — the rest of the time it's switcher-only.
        legs = self._legs(config or {})
        first, last = self._span(legs)
        if not (first and last):
            return False
        now = datetime.now(timezone.utc)
        return (first - SHOW_LEAD) <= now <= (last + SHOW_TRAIL)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        return 18.0
