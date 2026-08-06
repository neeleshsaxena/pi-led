"""Local news headlines.

Pulls recent headlines for a configured location (Google News RSS, no API key) and
scrolls them on the panel. Data/config/lifecycle live here (lead-owned); pixel
layout lives in render.py (UI-owned).

Set the location with the `place` config (default = the weather place / San
Francisco) or the NEWS_PLACE env var. The committed default is a generic city;
the real local place comes from the env/stored config, kept out of the repo.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext

from .news import NewsClient
from .render import render_news


class NewsApp(LedApp):
    id = "news"
    name = "News"

    def __init__(self) -> None:
        self.client: NewsClient | None = None
        self._headlines: list[str] = []

    def default_config(self) -> dict:
        return {"place": os.environ.get("NEWS_PLACE", os.environ.get("WEATHER_PLACE", "San Francisco"))}

    async def start(self) -> None:
        self.client = NewsClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        place = str(cfg.get("place", "San Francisco"))
        if self.client is not None:
            try:
                fresh = await self.client.headlines(place, limit=8)  # cached ~15 min
                if fresh:
                    self._headlines = fresh
            except Exception:  # noqa: BLE001 - fetch is best-effort; keep last headlines
                pass
        return render_news(self._headlines, place, ctx.tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # The ticker scrolls continuously; a full 8-headline loop is long, so dwell
        # for a readable slice (a few headlines) rather than a whole pass. If the UI
        # moves to paged cards, size this to items * per-page instead.
        return 18.0
