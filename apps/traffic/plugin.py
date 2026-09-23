"""Local traffic for the panel.

Two views:
  - `main` — incident alerts (crashes, roadwork, hazards) within `radius_km` of
             home, worst first, with the commute freeways (US-101 / I-280) boosted
             to the top.
  - `eta`  — live drive time to SF (TomTom), with minutes-of-delay vs free-flow —
             the actual "how bad is the commute right now" signal.

Data/config/lifecycle live here (lead-owned); pixel layout lives in render.py
(UI-owned). Config keys: `lat`/`lon` (center), `radius_km`, `commute_roads` (codes
boosted in `main`), and `sf_lat`/`sf_lon` (the eta destination). The committed
default is a generic city center; the real coordinates come from stored config or
TRAFFIC_LAT / TRAFFIC_LON — a home location, kept out of the repo. `main` reuses
the transit app's free 511 key; `eta` uses a TomTom key.
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
        self._events: dict[str, list[dict]] = {"main": []}
        self._eta: dict | None = None

    def views(self) -> list[ViewSpec]:
        # `main` = incident alerts near home (101/280 floated to the top); `eta` =
        # live drive time to SF. A separate "commute corridor incidents" view was
        # dropped — it was a redundant subset of `main` (same 511 feed) and almost
        # always empty; the live-congestion signal people want is the eta card.
        return [
            ViewSpec(id="main", label="Traffic"),
            ViewSpec(id="eta", label="SF drive time"),
        ]

    def default_config(self) -> dict:
        return {
            "lat": _env_float("TRAFFIC_LAT") or DEFAULT_LAT,
            "lon": _env_float("TRAFFIC_LON") or DEFAULT_LON,
            "radius_km": _env_float("TRAFFIC_RADIUS_KM") or DEFAULT_RADIUS_KM,
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

        if self.client is not None:
            try:
                radius = float(cfg.get("radius_km", DEFAULT_RADIUS_KM))
                evs = await self.client.events(lat, lon, radius)
                self._events["main"] = _boost(evs, roads)  # [] is a valid "all clear"
            except Exception:  # noqa: BLE001 - best-effort; keep last events
                pass

        return render_traffic(self._events.get("main", []), has_key=has_key, title="TRAFFIC", tick=ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Paged incidents; give each page time to be read (see render.py PAGE_SECS).
        return 12.0


def _boost(events: list[dict], roads) -> list[dict]:
    """Float commute-freeway incidents to the front of the local list."""
    want = {r.upper() for r in roads}
    pri = [e for e in events if e.get("code", "").upper() in want]
    rest = [e for e in events if e.get("code", "").upper() not in want]
    return pri + rest
