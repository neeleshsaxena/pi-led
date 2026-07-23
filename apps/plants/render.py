"""Plant watering reminder — pixel rendering (functional scaffold; UI polish TBD).

One group per frame (indoor / outdoor): a potted plant, the days-until-water as a
big number that goes NEGATIVE when overdue, a status line, and a droplet. Outdoor
frames show a rain-cloud + "RAIN-FED" when recent rain reset the clock.

Entry point: render_group(group, remaining, interval, rain_fed, tick).
`remaining` = interval - days_since_watered (>0 days left, 0 due today, <0 overdue).
See deploy/UI-ASKS.md — the negative-overdue treatment + plant art are UI-owned polish.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    CYAN,
    GRAY,
    GREEN,
    PX_BIG,
    PX_HUGE,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px_centered,
    filled_rect,
    new_canvas,
    pulse_color,
    scale_color,
)

BROWN = (156, 90, 52)
LEAF = (46, 176, 84)
WATER = (72, 162, 236)
SKY = (150, 175, 205)


def _plant(draw, cx: int, base_y: int) -> None:
    """A little potted plant: terracotta pot + stem + three leaves."""
    filled_rect(draw, cx - 6, base_y - 4, cx + 6, base_y, BROWN)                 # pot
    filled_rect(draw, cx - 7, base_y - 6, cx + 7, base_y - 5, scale_color(BROWN, 0.8))  # rim
    draw.line([(cx, base_y - 6), (cx, base_y - 14)], fill=scale_color(LEAF, 0.9))       # stem
    for dx, dy in ((-3, -11), (3, -12), (0, -16)):
        draw.ellipse([cx + dx - 3, base_y + dy - 2, cx + dx + 3, base_y + dy + 2], fill=LEAF)


def _droplet(draw, x: int, y: int, color) -> None:
    draw.polygon([(x, y - 3), (x - 2, y + 1), (x + 2, y + 1)], fill=color)
    draw.ellipse([x - 2, y, x + 2, y + 3], fill=color)


def _raincloud(draw, x: int, y: int) -> None:
    draw.ellipse([x - 5, y - 2, x + 5, y + 3], fill=scale_color(SKY, 0.9))
    for i in range(-3, 4, 3):
        draw.line([(x + i, y + 4), (x + i, y + 6)], fill=WATER)


def render_group(group, remaining, interval, rain_fed, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    label = "OUTDOOR" if group == "outdoor" else "INDOOR"
    draw_px_centered(draw, 1, label, fill=LEAF, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(LEAF, 0.55))

    if remaining < 0:
        col = pulse_color(RED, tick, period=1.0, min_factor=0.55)
        num, status = str(remaining), "OVERDUE!"
    elif remaining == 0:
        col, num, status = YELLOW, "0", "WATER TODAY"
    else:
        col = GREEN if remaining > 2 else YELLOW
        num, status = str(remaining), ("DAYS LEFT" if remaining != 1 else "DAY LEFT")
    size = PX_HUGE if len(num) == 1 else PX_BIG
    draw_px_centered(draw, 15, num, fill=col, size=size)
    draw_px_centered(draw, 38, status, fill=col if remaining < 0 else scale_color(WHITE, 0.9), size=PX_SMALL)

    _plant(draw, 11, 61)
    _droplet(draw, WIDTH - 10, 54, WATER if remaining <= 0 else scale_color(WATER, 0.45))
    if group == "outdoor" and rain_fed:
        _raincloud(draw, WIDTH - 11, 22)
        draw_micro_centered(draw, 47, "RAIN-FED", fill=CYAN)
    return img
