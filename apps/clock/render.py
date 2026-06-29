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
    GRAY,
    HEIGHT,
    PX_BIG,
    PX_SMALL,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro,
    draw_px,
    filled_rect,
    hsv_color,
    micro_text_width,
    new_canvas,
    px_text_width,
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


def _wave_divider(draw, tick: float, y_mid: int = 29) -> None:
    """Animated flowing divider between the two timezone bands: two thin sine
    waves drifting in opposite directions (a gentle interference shimmer). Lives
    in the dead space between the zones, so it adds life without eating room.
    Bright pixels only — flicker-safe."""
    x0, x1 = 2, WIDTH - 2
    back = [(x, int(round(y_mid + 2.0 * math.sin(x * 0.34 + tick * 1.6)))) for x in range(x0, x1)]
    draw.line(back, fill=(46, 92, 180))
    col = hsv_color(0.52 + 0.12 * math.sin(tick * 0.3), 0.85, 1.0)  # cool, drifting
    front = [(x, int(round(y_mid + 2.0 * math.sin(x * 0.34 - tick * 2.3)))) for x in range(x0, x1)]
    draw.line(front, fill=col)


# Per-zone accent: PST cool cyan, IST warm accent. Others fall back to cyan.
_ZONE_ACCENT = {"PST": CYAN, "IST": ACCENT}


def _zone(draw, y0: int, label: str, dt: datetime, cfg: dict) -> None:
    """One timezone band (~31px tall) at top y0: label + date (micro), big HH:MM
    with a breathing colon, AM/PM marker, and a seconds sweep bar."""
    accent = _ZONE_ACCENT.get(label, CYAN)
    hour24 = bool(cfg.get("hour24", False))
    sub = _subsecond(dt)

    # zone label (kenpixel small, accent) + date (micro, right, muted)
    draw_px(draw, (3, y0 + 1), label, fill=accent, size=PX_SMALL)
    if cfg.get("show_date", True):
        date_str = f"{_DOW[dt.weekday()]} {dt.day} {_MON[dt.month - 1]}"
        draw_micro(draw, (WIDTH - 3 - micro_text_width(date_str), y0 + 2), date_str, fill=GRAY)

    # big HH:MM (kenpixel) with a breathing colon
    hh, mm = _hh(dt, hour24), dt.strftime("%M")
    ty = y0 + 9
    x = 3
    draw_px(draw, (x, ty), hh, fill=WHITE, size=PX_BIG)
    x += px_text_width(hh, PX_BIG)
    b = 0.30 + 0.70 * (0.5 + 0.5 * math.cos(sub * math.tau))
    draw_px(draw, (x, ty), ":", fill=scale_color(WHITE, b), size=PX_BIG)
    x += px_text_width(":", PX_BIG)
    draw_px(draw, (x, ty), mm, fill=WHITE, size=PX_BIG)
    if not hour24:
        draw_px(draw, (WIDTH - 6, ty + 1), dt.strftime("%p")[0], fill=scale_color(accent, 0.9), size=PX_SMALL)

    # seconds sweep bar (fills across the minute)
    by = y0 + 27
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
    _wave_divider(draw, tick)
    return img


# ─── analog ──────────────────────────────────────────────────────────────────


def _hand(draw, cx, cy, angle, length, color, width=1) -> None:
    x = cx + math.cos(angle) * length
    y = cy + math.sin(angle) * length
    draw.line([cx, cy, x, y], fill=color, width=width)


_NUMERALS = ((0, "12"), (3, "3"), (6, "6"), (9, "9"))


def render_analog(now: datetime, cfg: dict, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    cx, cy, r = WIDTH // 2, HEIGHT // 2, 30
    sub = _subsecond(now)

    # cool rim with a faint breathing
    rim = pulse_color(CYAN, tick, period=4.0, min_factor=0.4)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=scale_color(rim, 0.6))

    # glowing second-sweep arc: grows from 12 o'clock around the dial each minute
    end = -90 + sub * 6.0
    arc_col = hsv_color(0.08, 0.95, 1.0)  # warm accent
    draw.arc([cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1], -90, end, fill=ACCENT)
    draw.arc([cx - r, cy - r, cx + r, cy + r], -90, end, fill=scale_color(arc_col, 0.55))

    # minor ticks at the 8 non-cardinal hours (cardinals get numerals instead)
    for i in range(12):
        if i % 3 == 0:
            continue
        a = math.radians(i * 30 - 90)
        outer, inner = r - 2, r - 5
        draw.line(
            [cx + math.cos(a) * inner, cy + math.sin(a) * inner,
             cx + math.cos(a) * outer, cy + math.sin(a) * outer],
            fill=scale_color(GRAY, 0.95),
        )

    # cardinal numerals (12 / 3 / 6 / 9), kenpixel, tucked just inside the rim
    for idx, txt in _NUMERALS:
        a = math.radians(idx * 30 - 90)
        nx = cx + math.cos(a) * (r - 8)
        ny = cy + math.sin(a) * (r - 8)
        w = px_text_width(txt, PX_SMALL)
        draw_px(draw, (int(nx - w / 2), int(ny - 3)), txt, fill=WHITE, size=PX_SMALL)

    h, m = now.hour % 12, now.minute
    _hand(draw, cx, cy, math.radians((h + m / 60) * 30 - 90), r * 0.46, WHITE, 2)
    _hand(draw, cx, cy, math.radians((m + sub / 60) * 6 - 90), r * 0.70, CYAN, 2)

    # second hand + a bright "comet head" riding its tip
    sa = math.radians(sub * 6 - 90)
    _hand(draw, cx, cy, sa, r * 0.80, ACCENT, 1)
    hx = cx + math.cos(sa) * (r * 0.80)
    hy = cy + math.sin(sa) * (r * 0.80)
    head = pulse_color(YELLOW, tick, period=0.5, min_factor=0.6)
    draw.ellipse([hx - 1, hy - 1, hx + 1, hy + 1], fill=head)
    # small counterweight on the opposite side
    _hand(draw, cx, cy, sa + math.pi, r * 0.16, scale_color(ACCENT, 0.8), 1)

    # breathing center hub
    hub = pulse_color(WHITE, tick, period=1.0, min_factor=0.5)
    draw.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=hub)
    return img
