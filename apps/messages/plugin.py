from __future__ import annotations

from PIL import Image

from pi_led_core.canvas import (
    BLUE,
    GREEN,
    ORANGE,
    RED,
    WHITE,
    YELLOW,
)
from pi_led_core.plugin import LedApp, RenderContext

from .render import render_message

# Named colors the admin can pick from for a message. (Data/config contract —
# web.py reads these for the color dropdown. The pixel layout lives in
# render.py, owned by the UI/UX workstream.)
COLORS: dict[str, tuple[int, int, int]] = {
    "white": WHITE,
    "red": RED,
    "green": GREEN,
    "yellow": YELLOW,
    "orange": ORANGE,
    "blue": BLUE,
}


class MessagesApp(LedApp):
    """Display a single static message typed in the admin. Text is uppercased
    (the 5x7 font is uppercase) and auto-fit to the panel."""

    id = "messages"
    name = "Message"

    def default_config(self) -> dict:
        return {"text": "Sunny Bunny", "color": "white", "viz": "solid"}

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        text = str(cfg.get("text", "")).upper()
        color = COLORS.get(str(cfg.get("color", "white")).lower(), WHITE)
        viz = str(cfg.get("viz", "solid"))
        return render_message(text, color, viz=viz, tick=ctx.tick)
