"""Reminders — pixel rendering (UI-owned).

Pages the active reminders one at a time: a checkbox glyph + the reminder text
(wrapped to fit) + an urgency-tinted date chip (LATE / TODAY / a date), with
paging dots below. An empty list gets a little "ALL CLEAR" celebration.

Entry point: render_reminders(items, tick), where each item is
(text, days_until|None, date_label) — days_until<0 overdue, 0 today, None undated.
Deliberately gentle: overdue reads as a warm "LATE" chip, not an alarm.
"""
from __future__ import annotations

import math

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    GRAY,
    GREEN,
    ORANGE,
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
    pulse_color,
    px_cap_height,
    px_text_width,
    scale_color,
    sparkle,
)

DWELL = 3.6           # seconds each reminder holds before paging to the next
_SOFT_RED = (240, 96, 84)   # a warm "late" — clear but not a klaxon
_CAP = px_cap_height(PX_SMALL)


def _urgency(days, label):
    """(chip_label, accent) for a reminder's due state. Undated → (None, white)."""
    if days is None:
        return None, scale_color(WHITE, 0.92)
    if days < 0:
        return "LATE", _SOFT_RED
    if days == 0:
        return "TODAY", ORANGE
    if days <= 2:
        return (label or "SOON"), YELLOW
    return (label or ""), GREEN


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


def _checkbox(draw, x: int, y: int, color, s: int = 7) -> None:
    draw.rectangle([x, y, x + s - 1, y + s - 1], outline=color)
    draw.point((x + 1, y + 1), fill=scale_color(color, 0.5))


def _chip(draw, cy: int, label: str, color) -> None:
    """A rounded date/urgency pill, centered horizontally at row top `cy`."""
    if not label:
        return
    w = px_text_width(label, PX_SMALL)
    pad = 4
    x0 = (WIDTH - (w + 2 * pad)) // 2
    x1 = x0 + w + 2 * pad
    draw.rounded_rectangle([x0, cy - 2, x1, cy + _CAP + 1], radius=3, fill=scale_color(color, 0.20))
    draw_px(draw, (x0 + pad, cy), label, fill=color, size=PX_SMALL)


def _dots(draw, idx: int, n: int, color) -> None:
    y = 61
    if n <= 1:
        return
    if n * 5 - 2 <= WIDTH - 8:            # dots fit
        total = n * 5 - 2
        x0 = (WIDTH - total) // 2
        for i in range(n):
            x = x0 + i * 5
            if i == idx:
                filled_rect(draw, x, y, x + 2, y + 2, color)
            else:
                draw.point((x + 1, y + 1), fill=scale_color(GRAY, 0.8))
    else:                                 # too many — compact "i/n"
        draw_micro_centered(draw, y, f"{idx + 1}/{n}", fill=scale_color(GRAY, 0.85))


def _all_clear(draw, tick: float):
    # a soft celebration: a breathing green check + sparkles
    sparkle(draw, tick, count=10, seed=3)
    cx, cy = WIDTH // 2, 26
    col = pulse_color(GREEN, tick, period=1.8, min_factor=0.7)
    draw.line([(cx - 6, cy), (cx - 1, cy + 6)], fill=col, width=2)
    draw.line([(cx - 1, cy + 6), (cx + 8, cy - 7)], fill=col, width=2)
    draw_px_centered(draw, 40, "ALL CLEAR", fill=GREEN, size=PX_SMALL)
    draw_micro_centered(draw, 52, "NOTHING DUE", fill=scale_color(GRAY, 0.8))


def render_reminders(items, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, "REMINDERS", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(ACCENT, 0.5))

    if not items:
        _all_clear(draw, tick)
        return img

    n = len(items)
    idx = int(tick / DWELL) % n
    text, days, label = items[idx]
    chip_label, accent = _urgency(days, label)

    lines = _wrap(text.upper(), WIDTH - 8)[:3]
    line_h = _CAP + 3
    block_h = len(lines) * line_h - 3
    # a checkbox row on top, then the wrapped text, then an optional chip —
    # centered as one group in the body band (checkbox never crowds wide text).
    group_h = _CAP + 3 + block_h + ((_CAP + 5) if chip_label else 0)
    top = 12 + max(0, ((59 - 12) - group_h) // 2)

    _checkbox(draw, (WIDTH - _CAP) // 2, top, accent)
    y = top + _CAP + 3
    for ln in lines:
        draw_px_centered(draw, y, ln, fill=WHITE, size=PX_SMALL)
        y += line_h
    if chip_label:
        _chip(draw, y, chip_label, accent)

    _dots(draw, idx, n, accent)
    return img
