"""Local traffic incidents for the panel.

Shows active incidents/construction on the freeways near a configured point
(default generic; overridden per-install to the real home coordinates). Data/
config/lifecycle live here (lead-owned); pixel layout lives in render.py (UI-owned).

Config: `lat` / `lon` (the center point) and `radius_km` (how far out to look).
The committed default is a generic city center; the real coordinates come from the
stored config or TRAFFIC_LAT / TRAFFIC_LON env — a home location, kept out of the
repo. Reuses the transit app's free 511 key (TRANSIT_API_KEY).
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .render import render_traffic
from .traffic import TrafficClient

# Generic committed default — downtown San Francisco. Reveals no home location;
# the real coordinates come from the stored config / TRAFFIC_LAT,TRAFFIC_LON.
DEFAULT_LAT = 37.7749
DEFAULT_LON = -122.4194
DEFAULT_RADIUS_KM = 6.0


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
        self._events: list[dict] = []

    def default_config(self) -> dict:
        return {
            "lat": _env_float("TRAFFIC_LAT") or DEFAULT_LAT,
            "lon": _env_float("TRAFFIC_LON") or DEFAULT_LON,
            "radius_km": _env_float("TRAFFIC_RADIUS_KM") or DEFAULT_RADIUS_KM,
        }

    async def start(self) -> None:
        self.client = TrafficClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        lat = float(cfg.get("lat", DEFAULT_LAT))
        lon = float(cfg.get("lon", DEFAULT_LON))
        radius = float(cfg.get("radius_km", DEFAULT_RADIUS_KM))
        has_key = bool(self.client and self.client.has_key)
        if self.client is not None:
            try:
                fresh = await self.client.events(lat, lon, radius)  # cached ~5 min
                self._events = fresh  # [] is a valid "all clear", so don't keep stale
            except Exception:  # noqa: BLE001 - best-effort; keep last events
                pass
        return render_traffic(self._events, has_key=has_key, tick=ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Paged incidents; give each page time to be read (see render.py PAGE_SECS).
        return 12.0
