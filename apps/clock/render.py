"""Visual layout for the clock app — owned by the UI/UX workstream.

Pure rendering: given a datetime + config (+ tick for animation), produce a
64x64 frame. No data/config logic lives here. Entry points:
    render_digital(now, cfg, tick) -> Image
    render_analog(now, cfg, tick)  -> Image
See deploy/UI-UX-WORKSTREAM.md for ownership boundaries.

Design notes: bright-on-black + readable 5x7 font (the 3x5 micro font is too
fine for the panel). Motion is smooth bright pixels (a flowing wave, a sweeping
arc, a breathing colon) — never dim full-field fills, which flicker.
"""
from __future__ import annotations

import math
from datetime import datetime

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GLYPH_W,
    GRAY,
    HEIGHT,
    WHITE,
    WIDTH,
    big_text_width,
    draw_big,
    draw_big_centered,
    draw_micro,
    filled_rect,
    hsv_color,
    micro_text_width,
    new_canvas,
    pulse_color,
    scale_color,
)

_DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _hh(now: datetime, hour24: bool) -> str:
    if hour24:
        return now.strftime("%H")
    return now.strftime("%I").lstrip("0") or "12"


def _subsecond(now: datetime) -> float:
    return now.second + now.microsecond / 1e6


# ─── digital ─────────────────────────────────────────────────────────────────


def _draw_waves(draw, tick: float, sub: float, y_mid: int = 52) -> None:
    """Two layered sine waves drifting across the lower band + a bright marker
    that rides the crest, advancing once per minute with the seconds. The cool,
    glanceable 'this clock is alive' element."""
    x0, x1 = 2, WIDTH - 2
    # back wave — slower, wider, steady cool blue
    back = []
    for x in range(x0, x1):
        y = y_mid + 5.0 * math.sin(x * 0.21 + tick * 1.3)
        back.append((x, int(round(y))))
    draw.line(back, fill=(46, 92, 180))
    # front wave — faster, color drifts through the cool end of the spectrum
    col = hsv_color(0.52 + 0.16 * math.sin(tick * 0.25), 0.9, 1.0)
    front = []
    for x in range(x0, x1):
        y = y_mid + 4.0 * math.sin(x * 0.30 + tick * 2.5)
        front.append((x, int(round(y))))
    draw.line(front, fill=col)
    # seconds marker rides the front wave (white, crisp)
    frac = sub / 60.0
    mx = x0 + int(frac * (x1 - x0 - 1))
    my = int(round(y_mid + 4.0 * math.sin(mx * 0.30 + tick * 2.5)))
    draw.ellipse([mx - 1, my - 1, mx + 1, my + 1], fill=WHITE)


# Per-zone accent: PST cool cyan, IST warm accent. Others fall back to cyan.
_ZONE_ACCENT = {"PST": CYAN, "IST": ACCENT}


def _zone(draw, y0: int, label: str, dt: datetime, cfg: dict) -> None:
    """One timezone band (~31px tall) at top y0: label + date (micro), big HH:MM
    with a breathing colon, AM/PM marker, and a seconds sweep bar."""
    accent = _ZONE_ACCENT.get(label, CYAN)
    hour24 = bool(cfg.get("hour24", False))
    sub = _subsecond(dt)

    # label (left) + date (right), micro font — secondary info
    draw_micro(draw, (3, y0 + 1), label, fill=accent)
    if cfg.get("show_date", True):
        date_str = f"{_DOW[dt.weekday()]} {dt.day} {_MON[dt.month - 1]}"
        draw_micro(draw, (WIDTH - 3 - micro_text_width(date_str), y0 + 1), date_str, fill=GRAY)

    # big HH:MM with breathing colon
    hh, mm = _hh(dt, hour24), dt.strftime("%M")
    ty = y0 + 8
    draw_big(draw, (3, ty), f"{hh}:{mm}", fill=WHITE, scale=2)
    colon_x = 3 + len(hh) * (GLYPH_W * 2 + 1)
    b = 0.30 + 0.70 * (0.5 + 0.5 * math.cos(sub * math.tau))
    draw_big(draw, (colon_x, ty), ":", fill=scale_color(WHITE, b), scale=2)
    if not hour24:
        draw_micro(draw, (WIDTH - 4, ty + 4), dt.strftime("%p")[0], fill=scale_color(accent, 0.9))

    # seconds sweep bar (fills across the minute)
    by = y0 + 26
    filled_rect(draw, 3, by, WIDTH - 4, by, scale_color(GRAY, 0.35))
    x1 = 3 + int((sub / 60.0) * (WIDTH - 7))
    if x1 > 3:
        filled_rect(draw, 3, by, x1, by, accent)


def render_digital(zones, cfg: dict, tick: float) -> Image.Image:
    """Dual-timezone clock: each (label, datetime) in `zones` gets a stacked band
    with time, date and a seconds bar. Built for PST + IST (see plugin.ZONES)."""
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    for i, (label, dt) in enumerate(zones[:2]):
        _zone(draw, i * 32, label, dt, cfg)
    draw.line([(2, 31), (WIDTH - 3, 31)], fill=scale_color(GRAY, 0.5))
    return img


# ─── analog ──────────────────────────────────────────────────────────────────


def _hand(draw, cx, cy, angle, length, color, width=1) -> None:
    x = cx + math.cos(angle) * length
    y = cy + math.sin(angle) * length
    draw.line([cx, cy, x, y], fill=color, width=width)


def render_analog(now: datetime, cfg: dict, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    cx, cy, r = WIDTH // 2, HEIGHT // 2, 30
    sub = _subsecond(now)

    # cool rim
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=scale_color(CYAN, 0.45))
    # glowing second-sweep arc: grows from 12 o'clock around the dial each minute
    end = -90 + sub * 6.0
    arc_col = hsv_color(0.08, 0.95, 1.0)  # warm accent
    draw.arc([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], -90, end, fill=ACCENT)
    draw.arc([cx - r, cy - r, cx + r, cy + r], -90, end, fill=scale_color(arc_col, 0.5))

    # hour ticks (brighter than before; cardinals in white)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        outer, inner = r - 2, r - (6 if i % 3 == 0 else 4)
        col = WHITE if i % 3 == 0 else scale_color(GRAY, 1.0)
        draw.line(
            [cx + math.cos(a) * inner, cy + math.sin(a) * inner,
             cx + math.cos(a) * outer, cy + math.sin(a) * outer],
            fill=col,
        )

    h, m = now.hour % 12, now.minute
    _hand(draw, cx, cy, math.radians((h + m / 60) * 30 - 90), r * 0.48, WHITE, 2)
    _hand(draw, cx, cy, math.radians((m + sub / 60) * 6 - 90), r * 0.72, CYAN, 1)
    _hand(draw, cx, cy, math.radians(sub * 6 - 90), r * 0.82, ACCENT, 1)

    # breathing center hub
    hub = pulse_color(WHITE, tick, period=1.0, min_factor=0.5)
    draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=hub)
    return img
