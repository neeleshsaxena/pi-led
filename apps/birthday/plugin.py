"""Birthday countdown app.

Counts down to a birthday (month/day, recurring each year) and escalates the
display as it nears — days → live HH:MM:SS on the last day → full celebration on
the day itself (see render.py). On the birthday the carousel lingers longer via
view_cycle_seconds. Data/config live here; pixel layout lives in render.py.
"""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .render import render_birthday

LOCAL_TZ = datetime.now().astimezone().tzinfo or ZoneInfo("UTC")


class BirthdayApp(LedApp):
    id = "birthday"
    name = "Birthday"

    def default_config(self) -> dict:
        # Generic placeholders for the public repo; set the real name/date via the
        # stored config or the BIRTHDAY_* env vars (kept out of committed code).
        return {
            "name": os.environ.get("BIRTHDAY_NAME", "Friend"),
            "month": int(os.environ.get("BIRTHDAY_MONTH", "1")),
            "day": int(os.environ.get("BIRTHDAY_DAY", "1")),
        }

    def _target(self, now: datetime, month: int, day: int) -> datetime:
        """The next occurrence of month/day at local midnight (this year, or next
        if it's already past)."""
        try:
            t = datetime(now.year, month, day, tzinfo=now.tzinfo)
        except ValueError:
            t = datetime(now.year, month, 28, tzinfo=now.tzinfo)
        if t.date() < now.date():
            t = t.replace(year=now.year + 1)
        return t

    def _countdown(self, config: dict) -> tuple[int, float]:
        cfg = config or {}
        now = datetime.now(LOCAL_TZ)
        month, day = int(cfg.get("month", 7)), int(cfg.get("day", 21))
        target = self._target(now, month, day)
        days = (target.date() - now.date()).days          # 0 = today (birthday)
        remaining = (target - now).total_seconds()          # to local midnight
        return days, remaining

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        days, remaining = self._countdown(cfg)
        return render_birthday(str(cfg.get("name", "Yasho")), days, remaining, ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # On the birthday itself, hold the celebration on the panel much longer.
        days, _ = self._countdown(config)
        if days <= 0:
            return float(os.environ.get("BIRTHDAY_CELEBRATE_DWELL", "30"))
        return None
