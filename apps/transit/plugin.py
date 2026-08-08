"""Real-time transit departures (Caltrain + local bus) for the panel.

Shows the next departures at a configured set of stops — by default a generic
Caltrain station, overridden per-install to the real local stops. Data/config/
lifecycle live here (lead-owned); pixel layout lives in render.py (UI-owned).

Config: `stops` is an ordered list of `{agency, stopcode, label}` — `agency` is a
511 operator id ("CT" Caltrain, "SM" SamTrans), `stopcode` the platform/stop id,
`label` the short name shown on the panel. The committed default is generic (SF
4th & King Caltrain); the real the Bay Area + bus stops live in the stored config /
TRANSIT_STOPS env, kept out of the repo. Needs a free 511 key (TRANSIT_API_KEY).
"""
from __future__ import annotations

import json
import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .render import render_transit
from .transit import TransitClient, minutes_until

# Generic committed default — SF 4th & King (northern terminus, reveals no
# personal location). Real local stops come from stored config / TRANSIT_STOPS.
DEFAULT_STOPS = [
    {"agency": "CT", "stopcode": "70011", "label": "SF NB"},
    {"agency": "CT", "stopcode": "70012", "label": "SF SB"},
]

MAX_PER_STOP = 3  # how many upcoming departures to surface per stop


def _env_stops() -> list[dict] | None:
    raw = os.environ.get("TRANSIT_STOPS", "").strip()
    if not raw:
        return None
    try:
        stops = json.loads(raw)
        return stops if isinstance(stops, list) and stops else None
    except (json.JSONDecodeError, ValueError):
        return None


class TransitApp(LedApp):
    id = "transit"
    name = "Transit"

    def __init__(self) -> None:
        self.client: TransitClient | None = None
        # last-good departures per (agency, stopcode), so a failed refresh keeps
        # showing the previous board instead of going blank.
        self._last: dict[tuple[str, str], list[dict]] = {}

    def default_config(self) -> dict:
        return {"stops": _env_stops() or [dict(s) for s in DEFAULT_STOPS]}

    async def start(self) -> None:
        self.client = TransitClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    def _stops(self, cfg: dict) -> list[dict]:
        stops = cfg.get("stops")
        return stops if isinstance(stops, list) and stops else list(DEFAULT_STOPS)

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        has_key = bool(self.client and self.client.has_key)
        board: list[dict] = []
        for stop in self._stops(cfg):
            agency = str(stop.get("agency", "")).strip()
            code = str(stop.get("stopcode", "")).strip()
            label = str(stop.get("label", code)).strip()
            deps = self._last.get((agency, code), [])
            if self.client is not None and agency and code:
                try:
                    fresh = await self.client.departures(agency, code)  # cached ~2 min
                    if fresh:
                        self._last[(agency, code)] = deps = fresh
                except Exception:  # noqa: BLE001 - best-effort; keep last board
                    pass
            # Recompute the minute countdown every frame from absolute ETAs, drop
            # anything already gone, keep the next few.
            rows = []
            for d in deps:
                m = minutes_until(d["expected"])
                if m < -1:
                    continue
                rows.append(
                    {
                        "line": d["line"],
                        "dest": d["dest"],
                        "direction": d["direction"],
                        "minutes": m,
                        "delayed": d["delayed"],
                    }
                )
                if len(rows) >= MAX_PER_STOP:
                    break
            board.append({"label": label, "agency": agency, "departures": rows})
        return render_transit(board, has_key=has_key, tick=ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # A departure board is glanceable; a short dwell is plenty. If the UI pages
        # between stops, size this to stops * per-page.
        return 10.0
