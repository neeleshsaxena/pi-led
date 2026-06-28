"""Clock — the reference plugin AND a genuinely useful app.

This is the simplest end-to-end example of the LedApp contract, meant to be
**copied as the starting point for a new LED app**:

    cp -r apps/clock apps/<your-app>     # then rename the class + id
    # add an instance to ALL_APPS in apps/__init__.py — that's it.

It shows the whole surface area without any external data:
  - `id` / `name`                  — identity (id is the config/state key)
  - `views()`                      — two admin-selectable views (digital/analog)
  - `default_config()`             — seeded config the admin can edit
  - `render(ctx)`                  — one 64x64 frame; `ctx.tick` drives animation
  - (optional) `start()`/`aclose()`— open/close clients; unused here (no I/O)

Ownership convention (same as the messages app): data/config/lifecycle live
here (lead-owned); the pixel layout lives in render.py (UI/UX-owned). See
deploy/UI-UX-WORKSTREAM.md.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .render import render_analog, render_digital

# Zones shown by the digital view, top-to-bottom. (label, tz). ZoneInfo handles
# DST automatically — "PST" is shown as a fixed label even when LA is on PDT.
ZONES = [
    ("PST", ZoneInfo("America/Los_Angeles")),
    ("IST", ZoneInfo("Asia/Kolkata")),
]


class ClockApp(LedApp):
    id = "clock"
    name = "Clock"

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="digital", label="Clock"),
            ViewSpec(id="analog", label="Clock Face"),
        ]

    def default_config(self) -> dict:
        # 12h by default (set hour24=True for 24h); show the date line.
        return {"hour24": False, "show_date": True}

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        if ctx.view == "analog":
            # analog stays a single face, on the first zone (PST)
            return render_analog(datetime.now(ZONES[0][1]), cfg, ctx.tick)
        zones = [(label, datetime.now(tz)) for label, tz in ZONES]
        return render_digital(zones, cfg, ctx.tick)
