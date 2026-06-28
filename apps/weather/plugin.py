"""Weather — current conditions + a short forecast from Open-Meteo (free, no key).

Data/config/lifecycle live here (lead-owned); pixel layout + icons live in
render.py (UI/UX-owned). Set your location with the `place` config (any city
name, geocoded by Open-Meteo) or the WEATHER_PLACE / WEATHER_UNIT env vars.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .client import WeatherClient
from .render import render_current, render_error, render_forecast


class WeatherApp(LedApp):
    id = "weather"
    name = "Weather"

    def __init__(self) -> None:
        self.client: WeatherClient | None = None

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="current", label="Weather"),
            ViewSpec(id="forecast", label="Forecast"),
        ]

    def default_config(self) -> dict:
        return {
            "place": os.environ.get("WEATHER_PLACE", "San Francisco"),
            "unit": os.environ.get("WEATHER_UNIT", "fahrenheit"),  # or "celsius"
        }

    async def start(self) -> None:
        self.client = WeatherClient()

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        place = str(cfg.get("place", "San Francisco"))
        unit = str(cfg.get("unit", "fahrenheit"))
        try:
            snap = await self.client.get(place=place, unit=unit)
        except Exception:
            return render_error(place)
        if ctx.view == "forecast":
            return render_forecast(snap, ctx.tick)
        return render_current(snap, ctx.tick)
