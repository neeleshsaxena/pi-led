from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:  # avoid importing FastAPI in the renderer process
    from fastapi import APIRouter


@dataclass
class ViewSpec:
    """One admin-selectable view a plugin offers. A plugin may expose several
    (e.g. worldcup -> today / next / standings)."""

    id: str
    label: str


@dataclass
class RenderContext:
    """Everything a plugin needs to render one 64x64 frame.

    `tick` is monotonic seconds (use for animation/pulse).
    `view` is which of the plugin's views is active (see LedApp.views()).
    `config` is the plugin's slice of controller state (see ControllerState).
    """

    tick: float
    view: str = "main"
    config: dict = field(default_factory=dict)
    width: int = 64
    height: int = 64


def make_view_key(plugin_id: str, view_id: str) -> str:
    return f"{plugin_id}:{view_id}"


def parse_view_key(key: str) -> tuple[str, str]:
    """'worldcup:today' -> ('worldcup', 'today'). Bare 'messages' -> ('messages', 'main')."""
    plugin_id, sep, view_id = key.partition(":")
    return plugin_id, (view_id if sep else "main")


class LedApp:
    """Base contract every LED project ("plugin") implements.

    A plugin is in-process: the single renderer owns the panel and calls the
    active plugin's `render()`. Plugins never touch the sink directly and never
    assume they are the only app. Web/admin concerns are optional and live in
    `admin_router()`, mounted by the controller's web process.
    """

    id: str = ""
    name: str = ""

    async def start(self) -> None:
        """Optional: open clients / warm caches before the first render."""

    async def aclose(self) -> None:
        """Optional: release clients on shutdown."""

    def views(self) -> list[ViewSpec]:
        """Admin-selectable views this plugin offers. Default: a single view."""
        return [ViewSpec(id="main", label=self.name or self.id)]

    async def render(self, ctx: RenderContext) -> Image.Image:
        """Return one RGB frame of size (ctx.width, ctx.height)."""
        raise NotImplementedError

    def default_config(self) -> dict:
        """Seed config used when state has nothing stored for this plugin."""
        return {}

    def admin_router(self) -> "APIRouter | None":
        """Optional per-plugin admin/config routes, mounted under /admin/apps/<id>."""
        return None
