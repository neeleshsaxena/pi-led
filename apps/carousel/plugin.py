"""Carousel — rotate the panel through a configured list of views.

This is an *orchestration* plugin: unlike a normal app it doesn't draw its own
frame. The controller (controller/runner.py) detects the carousel as the active
view and, on a dwell timer, expands it to the next view key in the rotation and
renders that underlying app instead. The plugin exists to:

  - appear in the admin view switcher (one selectable view, "Carousel"), and
  - own the rotation config: the ordered list of view keys + the per-view dwell.

Because nothing is drawn here there is no render.py (and no UI/UX-owned surface):
config/orchestration are lead-owned. Edit the rotation by changing `DEFAULT_VIEWS`
below, the stored `carousel` config (`views` / `dwell`), or LED_CAROUSEL_DWELL.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.canvas import new_canvas
from pi_led_core.plugin import LedApp, RenderContext

# Default rotation, in order. Each entry is a fully-qualified view key
# ("<plugin>:<view>"). Starting point per the user: today's World Cup matches,
# current weather, and the digital (dual-timezone) clock. Add more keys here —
# see any app's views() for valid ids (e.g. worldcup:next, clock:analog,
# weather:forecast, ambient:plasma, messages:main).
DEFAULT_VIEWS = [
    "worldcup:today",
    "worldcup:next",
    "worldcup:bracket",
    "worldcup:standings",
    "weather:current",
    "weather:forecast",
    "clock:digital",
]

# Seconds each view is held before advancing. Tunable per-deploy via env, and
# per-install via the stored `carousel` config's `dwell`.
DEFAULT_DWELL = float(os.environ.get("LED_CAROUSEL_DWELL", "10"))


class CarouselApp(LedApp):
    id = "carousel"
    name = "Carousel"

    def default_config(self) -> dict:
        # `views`: ordered list of view keys to cycle through.
        # `dwell`: seconds to hold each view before moving to the next.
        return {"views": list(DEFAULT_VIEWS), "dwell": DEFAULT_DWELL}

    async def render(self, ctx: RenderContext) -> Image.Image:
        # The controller intercepts the carousel before render() is ever reached
        # (it expands the carousel to the current rotation item and renders that
        # app instead). This is only a defensive fallback if something renders
        # the carousel directly — show a blank frame rather than crash.
        return new_canvas()
