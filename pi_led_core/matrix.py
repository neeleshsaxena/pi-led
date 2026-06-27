from __future__ import annotations

import os
import time
from pathlib import Path

from PIL import Image

from .canvas import HEIGHT, WIDTH

PREVIEW_PATH = Path(os.environ.get("LED_PREVIEW_PATH", "/tmp/led-preview.png"))
PREVIEW_SCALE = int(os.environ.get("LED_PREVIEW_SCALE", "8"))


class PNGSink:
    """Dev sink: writes each frame as a scaled-up PNG so it's visible in a browser.

    Uses write-then-rename so a polling browser never reads a half-written file.
    """

    def __init__(self, path: Path = PREVIEW_PATH, scale: int = PREVIEW_SCALE):
        self.path = path
        self.tmp_path = path.with_suffix(path.suffix + ".tmp")
        self.scale = scale
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def display(self, img: Image.Image) -> None:
        if self.scale != 1:
            img = img.resize((WIDTH * self.scale, HEIGHT * self.scale), Image.NEAREST)
        img.save(self.tmp_path, format="PNG")
        os.replace(self.tmp_path, self.path)


class HzellerSink:
    """Pi sink: pushes frames to the HUB75 panel via rpi-rgb-led-matrix."""

    def __init__(self) -> None:
        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        opts = RGBMatrixOptions()
        opts.rows = HEIGHT
        opts.cols = WIDTH
        opts.chain_length = 1
        opts.parallel = 1
        opts.hardware_mapping = "adafruit-hat"
        opts.gpio_slowdown = int(os.environ.get("LED_GPIO_SLOWDOWN", "2"))
        opts.brightness = int(os.environ.get("LED_BRIGHTNESS", "60"))
        # Keep the render loop as root. The library otherwise drops to the
        # 'daemon' user after init, but the renderer must keep reading
        # .state.json inside /home/pi (mode 0700) to pick up view changes
        # the web app writes — daemon can't traverse that. This is a dedicated
        # appliance, so staying root is acceptable. Override with
        # LED_DROP_PRIVS=1 if the state file ever lives somewhere world-readable.
        opts.drop_privileges = int(os.environ.get("LED_DROP_PRIVS", "0"))
        self.matrix = RGBMatrix(options=opts)

    def display(self, img: Image.Image) -> None:
        self.matrix.SetImage(img.convert("RGB"))


class TeeSink:
    """Drives the panel every frame and additionally writes a *throttled* PNG
    preview so the current panel content is viewable in a browser (e.g. at
    ledpanel.local/preview) for remote UI work.

    The PNG write is rate-limited and best-effort: it never blocks or breaks the
    panel. Safe on the Pi because rpi-rgb-led-matrix refreshes the panel from its
    own C thread, so an occasional PNG encode in Python doesn't affect timing.
    """

    def __init__(self, primary, preview: PNGSink, min_interval: float = 1.0):
        self.primary = primary
        self.preview = preview
        self.min_interval = min_interval
        self._last_preview = 0.0

    def display(self, img: Image.Image) -> None:
        self.primary.display(img)
        now = time.monotonic()
        if now - self._last_preview >= self.min_interval:
            self._last_preview = now
            try:
                self.preview.display(img)
            except Exception:  # noqa: BLE001 - preview must never break the panel
                pass


def get_sink():
    """Auto-detect: hzeller on Pi (if rgbmatrix installed), PNG sink otherwise.

    On the Pi the real panel is the output; we additionally tee a throttled PNG
    preview (LED_PI_PREVIEW=0 to disable, LED_PI_PREVIEW_INTERVAL to tune the
    seconds between preview frames) so panel content is viewable in a browser.
    """
    if os.environ.get("LED_SINK") == "png":
        return PNGSink()
    try:
        import rgbmatrix  # noqa: F401
    except ImportError:
        return PNGSink()
    panel = HzellerSink()
    if os.environ.get("LED_PI_PREVIEW", "1") == "0":
        return panel
    interval = float(os.environ.get("LED_PI_PREVIEW_INTERVAL", "1.0"))
    return TeeSink(panel, PNGSink(), min_interval=interval)
