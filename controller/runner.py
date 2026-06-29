from __future__ import annotations

import asyncio
import signal
import time

from PIL import Image

from apps import ALL_APPS
from pi_led_core.canvas import new_canvas
from pi_led_core.matrix import get_sink
from pi_led_core.plugin import RenderContext
from pi_led_core.registry import AppRegistry
from pi_led_core.state import ControllerState

from .config import DEFAULT_ACTIVE, FRAME_INTERVAL, TRANSITION_SECONDS

CAROUSEL_ID = "carousel"


class Controller:
    """The single panel owner. Reads the active view from ControllerState and
    renders that plugin's frame to the sink, crossfading on view changes."""

    def __init__(self) -> None:
        self.registry = AppRegistry(ALL_APPS)
        defaults = {a.id: a.default_config() for a in self.registry.all()}
        self.state = ControllerState(default_active=DEFAULT_ACTIVE, defaults=defaults)
        self.sink = get_sink()
        self._last_key: str | None = None
        self._last_img: Image.Image | None = None
        self._transition_from: Image.Image | None = None
        self._transition_start = 0.0
        # Carousel rotation state (only live while the active view is the carousel).
        self._in_carousel = False
        self._carousel_idx = 0
        self._carousel_anchor = 0.0

    def _start_transition(self) -> None:
        if self._last_img is not None and TRANSITION_SECONDS > 0:
            self._transition_from = self._last_img.copy()
            self._transition_start = time.monotonic()

    def _apply_transition(self, fresh: Image.Image) -> Image.Image:
        if self._transition_from is None:
            return fresh
        elapsed = time.monotonic() - self._transition_start
        if elapsed >= TRANSITION_SECONDS:
            self._transition_from = None
            return fresh
        alpha = max(0.0, min(1.0, elapsed / TRANSITION_SECONDS))
        return Image.blend(self._transition_from, fresh, alpha)

    def _rotatable(self, key: str) -> bool:
        """A view key is usable in the carousel rotation if it resolves to a real
        plugin that isn't the carousel itself (guards against self-recursion)."""
        app, _ = self.registry.resolve(key)
        return app is not None and app.id != CAROUSEL_ID

    def _carousel_expand(self, app, now: float) -> str:
        """The active view is the carousel: return the underlying view key to show
        right now, advancing through the configured list on the dwell timer."""
        cfg = self.state.config_for(app.id)
        views = [k for k in (cfg.get("views") or []) if self._rotatable(k)]
        if not views:
            return DEFAULT_ACTIVE  # nothing valid configured: degrade gracefully
        dwell = max(2.0, float(cfg.get("dwell", 10.0)))
        if not self._in_carousel:  # fresh entry into carousel mode: start clean
            self._in_carousel = True
            self._carousel_idx = 0
            self._carousel_anchor = now
        elapsed = now - self._carousel_anchor
        if elapsed >= dwell:
            steps = int(elapsed // dwell)
            self._carousel_idx += steps
            self._carousel_anchor += steps * dwell
        return views[self._carousel_idx % len(views)]

    async def _render_active(self) -> Image.Image:
        now = time.monotonic()
        key = self.state.active
        app, view_id = self.registry.resolve(key)
        if app is not None and app.id == CAROUSEL_ID:
            # Expand the carousel to whichever view is due now, then render that.
            key = self._carousel_expand(app, now)
            app, view_id = self.registry.resolve(key)
        else:
            self._in_carousel = False

        if key != self._last_key:
            print(f"[led] view -> {key}")
            self._start_transition()
            self._last_key = key
        if app is None:
            return new_canvas()  # unknown plugin: blank panel
        ctx = RenderContext(
            tick=now,
            view=view_id,
            config=self.state.config_for(app.id),
        )
        return await app.render(ctx)

    async def run(self) -> None:
        await self.registry.start_all()
        print(
            f"[led] sink={self.sink.__class__.__name__}  apps={self.registry.ids()}  "
            f"frame={FRAME_INTERVAL}s  fade={TRANSITION_SECONDS}s"
        )
        while True:
            try:
                fresh = await self._render_active()
                out = self._apply_transition(fresh)
                self.sink.display(out)
                self._last_img = fresh
            except Exception as e:  # noqa: BLE001 - one bad frame must not kill the loop
                print(f"[led] frame error: {type(e).__name__}: {e}")
            await asyncio.sleep(FRAME_INTERVAL)

    async def close(self) -> None:
        await self.registry.close_all()


async def main() -> None:
    controller = Controller()
    stop = asyncio.Event()

    def _signal(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            pass

    task = asyncio.create_task(controller.run())
    await stop.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await controller.close()
    print("[led] stopped")


if __name__ == "__main__":
    asyncio.run(main())
