"""Home Chef — curates Indian dinner options from what's in the pantry and
lets you plan the week; the panel shows today's picks.

Flow: mark what's in the pantry -> curated suggestions from what's actually
makeable -> slot dishes onto days (any number of dishes per day) -> the panel
shows whatever's slotted for today. Manage all of it from a self-contained
admin UI at /admin/apps/homechef/ (pantry, suggestions, dish library, weekly
menu). Pixel layout lives in render.py.

Data lives in the `homechef` config as one JSON blob (see default_config):
ingredients/dishes referenced by name (no database, so names are the natural
key), `available` is the set of ingredient names currently on hand, `menu` is
day -> list of dish names. Data/config/lifecycle here (lead-owned); pixel
layout in render.py (UI-owned); the admin forms in admin.py (large enough to
warrant its own module, unlike the simpler one-concern apps).
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from . import seed_data
from .render import render_today

TZ = ZoneInfo(os.environ.get("HOMECHEF_TZ", "America/Los_Angeles"))
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def today_day() -> str:
    return DAYS[datetime.now(TZ).date().weekday()]


class HomeChefApp(LedApp):
    id = "homechef"
    name = "Home Chef"

    def default_config(self) -> dict:
        return {
            "ingredients": list(seed_data.INGREDIENTS),
            "dishes": list(seed_data.DISHES),
            "available": [],
            "menu": {day: [] for day in DAYS},
        }

    def _today_dishes(self, cfg: dict) -> list[str]:
        menu = cfg.get("menu") or {}
        return list(menu.get(today_day()) or [])

    async def render(self, ctx: RenderContext) -> Image.Image:
        return render_today(today_day(), self._today_dishes(ctx.config or {}), ctx.tick)

    def has_content(self, view_id: str, config: dict) -> bool:
        # Skip the carousel slot entirely when nothing's planned for today.
        return bool(self._today_dishes(config or {}))

    def admin_router(self):
        from .admin import build_router

        return build_router()
