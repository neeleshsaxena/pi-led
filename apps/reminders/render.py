"""Reminders — pixel rendering (functional scaffold; UI polish TBD).

Scrolls the active reminders as a ticker: "WATER PLANTS · CALL MOM · JUL 28" moving
right→left, looping, each tinted by urgency (overdue red, today/soon amber, dated
green, undated white). Empty list shows an "ALL CLEAR" card.

Entry point: render_reminders(items, tick), where each item is
(text, days_until|None, date_label) — days_until<0 overdue, 0 today, None undated.
See deploy/UI-ASKS.md — the ticker treatment / per-item cards are UI-owned polish.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    GRAY,
    GREEN,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_cap_height,
    px_text_width,
    scale_color,
)

_SEP = "   •   "  # " · " separator between reminders


def _seg(text: str, days, label: str) -> tuple[str, tuple[int, int, int]]:
    text = text.upper()
    if days is None:
        return text, WHITE
    if days < 0:
        return f"{text} - LATE", RED
    if days == 0:
        return f"{text} - TODAY", YELLOW
    if days <= 2:
        return f"{text} - {label}", YELLOW
    return f"{text} - {label}", GREEN


def render_reminders(items, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, "REMINDERS", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(ACCENT, 0.5))

    if not items:
        draw_px_centered(draw, 24, "ALL CLEAR", fill=GREEN, size=PX_SMALL)
        draw_micro_centered(draw, 40, "NOTHING DUE", fill=scale_color(GRAY, 0.8))
        return img

    # build the scrolling strip of colored segments
    parts = [(*_seg(*it),) for it in items]  # (text, color)
    parts = [(t + _SEP, c) for t, c in parts]
    widths = [px_text_width(t, PX_SMALL) for t, _ in parts]
    total = max(1, sum(widths))
    h = px_cap_height(PX_SMALL) + 2
    strip = Image.new("RGB", (total, h), (0, 0, 0))
    sd = ImageDraw.Draw(strip)
    x = 0
    for (t, c), w in zip(parts, widths):
        draw_px(sd, (x, 0), t, fill=c, size=PX_SMALL)
        x += w

    off = int((tick * 16) % total)
    view = Image.new("RGB", (WIDTH, h), (0, 0, 0))
    view.paste(strip, (-off, 0))
    view.paste(strip, (total - off, 0))  # second copy for a seamless loop
    img.paste(view, (0, 26))

    n = len(items)
    draw_micro_centered(draw, 46, f"{n} ACTIVE" if n != 1 else "1 ACTIVE", fill=scale_color(GRAY, 0.8))
    return img
