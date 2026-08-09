"""SFO flight board — next departures + arrivals.

Data/config/lifecycle live here (lead-owned); pixel layout lives in render.py
(UI-owned). One AeroDataBox call fetches the whole board; we trim it to the next
few flights each way for the panel.

Config: `icao` (airport, default KSFO), `hours` (look-ahead window), and `filters`
— {airlines: [IATA...], cities: [name/iata...], numbers: ["UA523"...]}. Filters
are display-only (they cost no extra API budget) and empty by default; the plumbing
is here so a "watchlist"/airline/city filter can be turned on later from the UI.
Needs a free AeroDataBox RapidAPI key (AERODATABOX_API_KEY), device-only.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .flights import FlightsClient
from .render import render_flights

DEFAULT_ICAO = os.environ.get("FLIGHTS_ICAO", "KSFO")
MAX_PER_SECTION = 6  # how many upcoming flights each way to surface


def _norm(s: str) -> str:
    return str(s or "").strip().upper()


def _match(flight: dict, filters: dict) -> bool:
    """True if the flight passes the (optional) filters. Empty filters => all."""
    airlines = {_norm(a) for a in (filters.get("airlines") or [])}
    cities = {_norm(c) for c in (filters.get("cities") or [])}
    numbers = {_norm(n).replace(" ", "") for n in (filters.get("numbers") or [])}
    if not (airlines or cities or numbers):
        return True
    num = _norm(flight.get("number")).replace(" ", "")
    if numbers and num in numbers:
        return True
    # airline by the IATA prefix of the flight number (e.g. "UA" from "UA 523")
    if airlines and num[:2] in airlines:
        return True
    if cities and (_norm(flight.get("iata")) in cities or _norm(flight.get("city")) in cities):
        return True
    return False


class FlightsApp(LedApp):
    id = "flights"
    name = "Flights"

    def __init__(self) -> None:
        self.client: FlightsClient | None = None
        self._board: dict = {"departures": [], "arrivals": []}

    def default_config(self) -> dict:
        return {
            "icao": DEFAULT_ICAO,
            "hours": 8,
            "filters": {"airlines": [], "cities": [], "numbers": []},
        }

    async def start(self) -> None:
        self.client = FlightsClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        icao = str(cfg.get("icao", DEFAULT_ICAO))
        hours = int(cfg.get("hours", 8))
        filters = cfg.get("filters") or {}
        has_key = bool(self.client and self.client.has_key)
        if self.client is not None and has_key:
            try:
                fresh = await self.client.board(icao, hours)  # cached ~30 min
                if fresh.get("departures") or fresh.get("arrivals"):
                    self._board = fresh
            except Exception:  # noqa: BLE001 - best-effort; keep last board
                pass
        dep = [f for f in self._board["departures"] if _match(f, filters)][:MAX_PER_SECTION]
        arr = [f for f in self._board["arrivals"] if _match(f, filters)][:MAX_PER_SECTION]
        return render_flights(dep, arr, has_key=has_key, tick=ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Paged one flight at a time; give the rotation time to show a few.
        return 16.0
