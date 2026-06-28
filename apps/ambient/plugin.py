"""Ambient — always-on generative eye candy (no external data).

Each view is a visual effect (plasma / matrix / fire / starfield / life). The
effects (and their per-frame state) live in render.py (UI/UX-owned); this plugin
just instantiates the active effect lazily and keeps it across frames, resetting
when the view changes.
"""
from __future__ import annotations

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .render import EFFECTS

_LABELS = {
    "plasma": "Plasma",
    "matrix": "Matrix Rain",
    "fire": "Fire",
    "starfield": "Starfield",
    "life": "Game of Life",
}


class AmbientApp(LedApp):
    id = "ambient"
    name = "Ambient"

    def __init__(self) -> None:
        self._effects: dict[str, object] = {}

    def views(self) -> list[ViewSpec]:
        return [ViewSpec(id=k, label=_LABELS.get(k, k.title())) for k in EFFECTS]

    def _effect(self, view: str):
        if view not in EFFECTS:
            view = next(iter(EFFECTS))
        if view not in self._effects:
            self._effects[view] = EFFECTS[view]()
        return self._effects[view]

    async def render(self, ctx: RenderContext) -> Image.Image:
        return self._effect(ctx.view).render(ctx.tick)
