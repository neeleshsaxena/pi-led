"""Plant watering reminder.

Two groups, each a view: indoor plants (water every N days) and outdoor plants
(same, but recent rain at your location counts as a watering, so the clock resets
to the last rain day). The days-until-water goes negative when overdue.

"I watered them" = stamp today's date for a group; a POST route (admin_router) does
that, so the admin UI can offer a per-group button. Data/config/lifecycle live here
(lead-owned); pixel layout lives in render.py (UI-owned).
"""
from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .rain import RainClient
from .render import render_group

TZ = ZoneInfo(os.environ.get("PLANTS_TZ", "America/Los_Angeles"))
SWAP_SECONDS = float(os.environ.get("PLANTS_SWAP", "6"))  # seconds per group in the single view


def _parse_date(s) -> date | None:
    try:
        return date.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


class PlantApp(LedApp):
    id = "plants"
    name = "Plants"

    def __init__(self) -> None:
        self.rain: RainClient | None = None
        self._last_rain: date | None = None
        self._swap_anchor = 0.0   # phase origin for the indoor<->outdoor swap
        self._last_tick = 0.0

    def default_config(self) -> dict:
        return {
            "indoor_interval": int(os.environ.get("PLANTS_INDOOR_DAYS", "7")),
            "outdoor_interval": int(os.environ.get("PLANTS_OUTDOOR_DAYS", "4")),
            "indoor_watered": "",   # ISO date "YYYY-MM-DD"; empty = assume today
            "outdoor_watered": "",
            "place": os.environ.get("PLANTS_PLACE", os.environ.get("WEATHER_PLACE", "San Francisco")),
            "rain_threshold_mm": float(os.environ.get("PLANTS_RAIN_MM", "1.0")),
        }

    def views(self) -> list[ViewSpec]:
        # One view; the plugin cycles indoor <-> outdoor within it (each group keeps
        # its own counter), reusing the full-panel per-group render.
        return [ViewSpec(id="main", label="Plant Watering")]

    async def start(self) -> None:
        self.rain = RainClient()

    async def aclose(self) -> None:
        if self.rain:
            await self.rain.close()

    def _remaining(self, cfg: dict, group: str) -> tuple[int, bool]:
        """(days_until_water, rain_fed). Negative days == overdue. For outdoor, the
        reference watering is the later of the manual date and the last rain day."""
        today = datetime.now(TZ).date()
        interval = int(cfg.get(f"{group}_interval", 7 if group == "indoor" else 4))
        watered = _parse_date(cfg.get(f"{group}_watered")) or today
        rain_fed = False
        if group == "outdoor" and self._last_rain and self._last_rain > watered:
            watered = self._last_rain  # rain counts as a watering
            rain_fed = True
        days_since = (today - watered).days
        return interval - days_since, rain_fed

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        # Alternate indoor -> outdoor within the single view. Restart at indoor on
        # (re)entry so a carousel visit always shows both groups in order.
        if ctx.tick - self._last_tick > 2.0:
            self._swap_anchor = ctx.tick
        self._last_tick = ctx.tick
        phase = (ctx.tick - self._swap_anchor) % (2 * SWAP_SECONDS)
        group = "indoor" if phase < SWAP_SECONDS else "outdoor"

        if group == "outdoor" and self.rain is not None:
            try:
                self._last_rain = await self.rain.last_rain_date(
                    str(cfg.get("place", "San Francisco")),
                    float(cfg.get("rain_threshold_mm", 1.0)),
                )
            except Exception:  # noqa: BLE001 - rain lookup is best-effort
                pass
        remaining, rain_fed = self._remaining(cfg, group)
        interval = int(cfg.get(f"{group}_interval", 7 if group == "indoor" else 4))
        return render_group(group, remaining, interval, rain_fed, ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Dwell long enough for the carousel to show both groups (one swap each).
        return 2 * SWAP_SECONDS

    def admin_router(self):
        """POST /admin/apps/plants/watered  (form: group=indoor|outdoor) — stamp
        today's date for that group, resetting its counter. The admin template adds
        the buttons (UI-owned); this is the backend they hit."""
        from fastapi import APIRouter, Form
        from fastapi.responses import RedirectResponse

        from pi_led_core.state import ControllerState

        router = APIRouter()

        @router.post("/watered")
        def watered(group: str = Form("indoor")) -> RedirectResponse:
            key = "outdoor_watered" if group == "outdoor" else "indoor_watered"
            ControllerState().set_config("plants", {key: datetime.now(TZ).date().isoformat()})
            return RedirectResponse("/admin", status_code=303)

        return router
