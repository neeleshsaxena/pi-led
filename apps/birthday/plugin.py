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

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .render import render_birthday, render_milestone

# The countdown is pinned to a real timezone rather than the host's local time,
# so the day flips at midnight in THAT zone no matter where this runs.
DEFAULT_TZ = os.environ.get("BIRTHDAY_TZ", "America/Los_Angeles")  # PST/PDT
SECONDARY_TZ = os.environ.get("BIRTHDAY_TZ2", "Asia/Kolkata")      # IST, shown briefly


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
            "tz": DEFAULT_TZ,
            # Monthly-milestone view (e.g. a baby's "N months" card). Give a
            # milestone_dob (YYYY-MM-DD) to auto-count, or a fixed milestone_months.
            "milestone_name": os.environ.get("MILESTONE_NAME", "Little One"),
            "milestone_dob": os.environ.get("MILESTONE_DOB", ""),
            "milestone_months": int(os.environ.get("MILESTONE_MONTHS", "0")),
        }

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="main", label="Birthday"),
            ViewSpec(id="milestone", label="Month Milestone"),
        ]

    def _months_old(self, config: dict) -> tuple[int, bool]:
        """(months_elapsed, is_milestone_day). Computed from milestone_dob when
        set; otherwise falls back to the fixed milestone_months."""
        cfg = config or {}
        dob = str(cfg.get("milestone_dob") or "").strip()
        if dob:
            try:
                y, m, d = (int(p) for p in dob.split("-"))
                now = datetime.now(self._zone(cfg))
                months = (now.year - y) * 12 + (now.month - m) - (1 if now.day < d else 0)
                return max(0, months), now.day == d
            except Exception:  # noqa: BLE001 - a bad DOB must not break the panel
                pass
        return max(0, int(cfg.get("milestone_months", 0) or 0)), False

    def _zone(self, config: dict) -> ZoneInfo:
        """The timezone the countdown is measured in (the day flips at midnight
        here), independent of the host's system timezone."""
        try:
            return ZoneInfo(str((config or {}).get("tz") or DEFAULT_TZ))
        except Exception:  # noqa: BLE001 - bad tz name must not break the panel
            return ZoneInfo("America/Los_Angeles")

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
        now = datetime.now(self._zone(cfg))
        month, day = int(cfg.get("month", 7)), int(cfg.get("day", 21))
        target = self._target(now, month, day)
        days = (target.date() - now.date()).days          # 0 = today (birthday)
        remaining = (target - now).total_seconds()          # to midnight in that zone
        return days, remaining

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        if ctx.view == "milestone":
            months, is_day = self._months_old(cfg)
            return render_milestone(
                str(cfg.get("milestone_name", "Little One")), months, is_day, ctx.tick
            )
        days, remaining = self._countdown(cfg)
        return render_birthday(str(cfg.get("name", "Friend")), days, remaining, ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Linger on the panel when it's actually the big day.
        if view_id == "milestone":
            _, is_day = self._months_old(config)
            return float(os.environ.get("MILESTONE_DWELL", "20")) if is_day else None
        days, _ = self._countdown(config)
        if days <= 0:
            return float(os.environ.get("BIRTHDAY_CELEBRATE_DWELL", "30"))
        return None
