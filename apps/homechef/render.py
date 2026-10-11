"""Home Chef — pixel rendering (UI-owned).

Shows what's planned for today. Multiple dishes page one at a time (name
wrapped to fit + paging dots below), same convention as reminders.py. Nothing
planned -> a quiet placeholder (the carousel skips this view entirely via
has_content, so it's only seen if selected directly from the admin switcher).

Entry point: render_today(day, dishes, tick), where `dishes` is a list of
dish-name strings for that day.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    GRAY,
    PX_SMALL,
    WHITE,
    WIDTH,
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_cap_height,
    px_text_width,
    scale_color,
)

DWELL = 4.0  # seconds each dish holds before paging to the next
_CAP = px_cap_height(PX_SMALL)


def _wrap(text: str, maxw: int) -> list[str]:
    """Greedy word-wrap to `maxw` px in PX_SMALL; hard-breaks over-long words."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if px_text_width(trial, PX_SMALL) <= maxw:
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while px_text_width(word, PX_SMALL) > maxw and len(word) > 1:
            cut = len(word)
            while cut > 1 and px_text_width(word[:cut], PX_SMALL) > maxw:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


def _dots(draw, idx: int, n: int, color) -> None:
    y = 61
    if n <= 1:
        return
    total = n * 5 - 2
    x0 = (WIDTH - total) // 2
    for i in range(n):
        x = x0 + i * 5
        if i == idx:
            filled_rect(draw, x, y, x + 2, y + 2, color)
        else:
            draw.point((x + 1, y + 1), fill=scale_color(GRAY, 0.8))


def render_today(day: str, dishes: list[str], tick: float = 0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, day.upper(), fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(ACCENT, 0.5))

    if not dishes:
        draw_px_centered(draw, 28, "NOTHING", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        draw_px_centered(draw, 38, "PLANNED YET", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    n = len(dishes)
    idx = int(tick / DWELL) % n
    lines = _wrap(dishes[idx].upper(), WIDTH - 8)[:3]
    line_h = _CAP + 3
    total_h = len(lines) * line_h - 3
    top = 12 + max(0, ((59 - 12) - total_h) // 2)

    y = top
    for ln in lines:
        draw_px_centered(draw, y, ln, fill=WHITE, size=PX_SMALL)
        y += line_h

    _dots(draw, idx, n, ACCENT)
    return img
