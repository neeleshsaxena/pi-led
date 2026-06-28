"""Visual layout for the clock app — owned by the UI/UX workstream.

Pure rendering: given a datetime + config (+ tick for animation), produce a
64x64 frame. No data/config logic lives here. Entry points:
    render_digital(now, cfg, tick) -> Image
    render_analog(now, cfg, tick)  -> Image
See deploy/UI-UX-WORKSTREAM.md for ownership boundaries.
"""
from __future__ import annotations

import math
from datetime import datetime

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GRAY,
    HEIGHT,
    WHITE,
    WIDTH,
    draw_big_centered,
    draw_micro_centered,
    filled_rect,
    new_canvas,
    scale_color,
)

_DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _hh(now: datetime, hour24: bool) -> str:
    if hour24:
        return now.strftime("%H")
    return now.strftime("%I").lstrip("0") or "12"


def render_digital(now: datetime, cfg: dict, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    hour24 = bool(cfg.get("hour24", False))

    hh, mm = _hh(now, hour24), now.strftime("%M")
    # Colon blinks once a second (space keeps the layout from shifting).
    sep = ":" if now.second % 2 == 0 else " "
    draw_big_centered(draw, 21, f"{hh}{sep}{mm}", fill=WHITE, scale=2)

    if not hour24:
        draw_micro_centered(draw, 8, now.strftime("%p"), fill=ACCENT)

    if cfg.get("show_date", True):
        date_str = f"{_DOW[now.weekday()]}  {now.day} {_MON[now.month - 1]}"
        draw_micro_centered(draw, 43, date_str, fill=CYAN)

    # Seconds sweep: a thin progress bar that fills across the minute.
    frac = (now.second + now.microsecond / 1e6) / 60.0
    x1 = 4 + int(frac * (WIDTH - 8))
    filled_rect(draw, 4, 54, WIDTH - 5, 55, scale_color(GRAY, 0.4))  # track
    if x1 > 4:
        filled_rect(draw, 4, 54, x1, 55, ACCENT)                      # fill
    return img


def _hand(draw, cx, cy, angle, length, color, width=1) -> None:
    x = cx + math.cos(angle) * length
    y = cy + math.sin(angle) * length
    draw.line([cx, cy, x, y], fill=color, width=width)


def render_analog(now: datetime, cfg: dict, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    cx, cy, r = WIDTH // 2, HEIGHT // 2, 30

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=scale_color(GRAY, 0.7))
    # Hour ticks (12 / 3 / 6 / 9 brighter).
    for i in range(12):
        a = math.radians(i * 30 - 90)
        outer, inner = r - 1, r - (5 if i % 3 == 0 else 3)
        draw.line(
            [cx + math.cos(a) * inner, cy + math.sin(a) * inner,
             cx + math.cos(a) * outer, cy + math.sin(a) * outer],
            fill=WHITE if i % 3 == 0 else scale_color(GRAY, 0.9),
        )

    h, m = now.hour % 12, now.minute
    s = now.second + now.microsecond / 1e6  # smooth sweeping second hand
    _hand(draw, cx, cy, math.radians((h + m / 60) * 30 - 90), r * 0.50, WHITE, 2)
    _hand(draw, cx, cy, math.radians((m + s / 60) * 6 - 90), r * 0.74, CYAN, 1)
    _hand(draw, cx, cy, math.radians(s * 6 - 90), r * 0.84, ACCENT, 1)
    draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=WHITE)
    return img
