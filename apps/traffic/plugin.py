"""Local traffic incidents for the panel.

Two views:
  - `main`    — everything within `radius_km` of home, worst first, but with the
                commute freeways (US-101 / I-280) boosted to the top.
  - `commute` — just the commute corridor (US-101 / I-280) out to
                `commute_radius_km`, ordered nearest-first (home → the city), for
                a "how's my drive to SF" glance.

Data/config/lifecycle live here (lead-owned); pixel layout lives in render.py
(UI-owned). Config keys: `lat`/`lon` (center), `radius_km`, `commute_radius_km`,
and `commute_roads` (base codes). The committed default is a generic city center;
the real coordinates come from stored config or TRAFFIC_LAT / TRAFFIC_LON — a home
location, kept out of the repo. Reuses the transit app's free 511 key.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .render import render_eta, render_traffic
from .routing import RoutingClient
from .traffic import TrafficClient

# Generic committed default — downtown San Francisco. Reveals no home location;
# the real coordinates come from the stored config / TRAFFIC_LAT,TRAFFIC_LON.
DEFAULT_LAT = 37.7749
DEFAULT_LON = -122.4194
DEFAULT_RADIUS_KM = 6.0
DEFAULT_COMMUTE_RADIUS_KM = 28.0
DEFAULT_COMMUTE_ROADS = ["US-101", "I-280"]
# ETA destination default — Salesforce Transit Center, downtown SF (generic).
DEFAULT_SF_LAT = 37.7896
DEFAULT_SF_LON = -122.3968


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


class TrafficApp(LedApp):
    id = "traffic"
    name = "Traffic"

    def __init__(self) -> None:
        self.client: TrafficClient | None = None
        self.routing: RoutingClient | None = None
        self._events: dict[str, list[dict]] = {"main": [], "commute": []}
        self._eta: dict | None = None

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="main", label="Traffic"),
            ViewSpec(id="commute", label="Commute (101)"),
            ViewSpec(id="eta", label="SF drive time"),
        ]

    def default_config(self) -> dict:
        return {
            "lat": _env_float("TRAFFIC_LAT") or DEFAULT_LAT,
            "lon": _env_float("TRAFFIC_LON") or DEFAULT_LON,
            "radius_km": _env_float("TRAFFIC_RADIUS_KM") or DEFAULT_RADIUS_KM,
            "commute_radius_km": _env_float("TRAFFIC_COMMUTE_KM") or DEFAULT_COMMUTE_RADIUS_KM,
            "commute_roads": list(DEFAULT_COMMUTE_ROADS),
            "sf_lat": _env_float("TRAFFIC_SF_LAT") or DEFAULT_SF_LAT,
            "sf_lon": _env_float("TRAFFIC_SF_LON") or DEFAULT_SF_LON,
        }

    async def start(self) -> None:
        self.client = TrafficClient()
        self.routing = RoutingClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()
        if self.routing:
            await self.routing.close()

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        lat = float(cfg.get("lat", DEFAULT_LAT))
        lon = float(cfg.get("lon", DEFAULT_LON))
        roads = cfg.get("commute_roads") or DEFAULT_COMMUTE_ROADS

        if ctx.view == "eta":
            has_key = bool(self.routing and self.routing.has_key)
            if self.routing is not None and has_key:
                try:
                    sf_lat = float(cfg.get("sf_lat", DEFAULT_SF_LAT))
                    sf_lon = float(cfg.get("sf_lon", DEFAULT_SF_LON))
                    fresh = await self.routing.eta(lat, lon, sf_lat, sf_lon)  # cached ~3 min
                    if fresh:
                        self._eta = fresh
                except Exception:  # noqa: BLE001 - best-effort; keep last eta
                    pass
            return render_eta(self._eta, has_key=has_key, dest="SF", tick=ctx.tick)

        has_key = bool(self.client and self.client.has_key)
        commute = ctx.view == "commute"

        if self.client is not None:
            try:
                if commute:
                    radius = float(cfg.get("commute_radius_km", DEFAULT_COMMUTE_RADIUS_KM))
                    evs = await self.client.events(lat, lon, radius, roads=roads, sort="distance")
                else:
                    radius = float(cfg.get("radius_km", DEFAULT_RADIUS_KM))
                    evs = await self.client.events(lat, lon, radius)
                    evs = _boost(evs, roads)
                self._events[ctx.view] = evs  # [] is a valid "all clear"
            except Exception:  # noqa: BLE001 - best-effort; keep last events
                pass

        title = "101 TO SF" if commute else "TRAFFIC"
        return render_traffic(self._events.get(ctx.view, []), has_key=has_key, title=title, tick=ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Paged incidents; give each page time to be read (see render.py PAGE_SECS).
        return 12.0


def _boost(events: list[dict], roads) -> list[dict]:
    """Float commute-freeway incidents to the front of the local list."""
    want = {r.upper() for r in roads}
    pri = [e for e in events if e.get("code", "").upper() in want]
    rest = [e for e in events if e.get("code", "").upper() not in want]
    return pri + rest
