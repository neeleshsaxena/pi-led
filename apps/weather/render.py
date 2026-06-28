"""Visual layout + weather icons for the weather app — UI/UX-owned.

Pure rendering: WeatherSnapshot -> 64x64 frame. Entry points:
    render_current(snap, tick)  -> Image
    render_forecast(snap, tick) -> Image
    render_error(place)         -> Image
See deploy/UI-UX-WORKSTREAM.md for ownership boundaries.
"""
from __future__ import annotations

import math
import unicodedata

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    BLUE,
    CYAN,
    GRAY,
    HEIGHT,
    WHITE,
    WIDTH,
    YELLOW,
    big_text_width,
    draw_big,
    draw_micro,
    draw_micro_centered,
    new_canvas,
    pulse_color,
    scale_color,
)

_CLOUD = (150, 160, 180)
_CLOUD_DK = (90, 100, 120)
_SUN = (255, 200, 40)
_MOON = (210, 220, 245)
_RAINDROP = (90, 170, 255)
_SNOW = (220, 235, 255)
_BOLT = (255, 225, 60)


def _ascii(s: str) -> str:
    norm = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in norm if not unicodedata.combining(c)).upper()


def _degree(draw, x: int, y: int, color) -> None:
    """A tiny degree ring at (x, y) top-left of a ~3px box."""
    draw.ellipse([x, y, x + 2, y + 2], outline=color)


# ── weather icons ────────────────────────────────────────────────────────────


def _cloud(draw, cx: int, cy: int, r: float, color) -> None:
    """Puffy cloud centered ~(cx, cy), width ~2r."""
    s = r
    draw.ellipse([cx - s, cy - s * 0.5, cx - s * 0.1, cy + s * 0.6], fill=color)
    draw.ellipse([cx - s * 0.5, cy - s, cx + s * 0.5, cy + s * 0.4], fill=color)
    draw.ellipse([cx + s * 0.1, cy - s * 0.5, cx + s, cy + s * 0.6], fill=color)
    draw.rectangle([cx - s, cy + s * 0.1, cx + s, cy + s * 0.6], fill=color)


def _sun(draw, cx: int, cy: int, r: float, tick: float, color=_SUN) -> None:
    rays = scale_color(color, 0.85)
    n = 8
    spin = tick * 0.6
    for i in range(n):
        a = spin + i * (math.tau / n)
        x1, y1 = cx + math.cos(a) * (r + 1), cy + math.sin(a) * (r + 1)
        x2, y2 = cx + math.cos(a) * (r + 4), cy + math.sin(a) * (r + 4)
        draw.line([x1, y1, x2, y2], fill=rays)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def _moon(draw, cx: int, cy: int, r: float) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_MOON)
    draw.ellipse([cx - r + r * 0.7, cy - r, cx + r + r * 0.7, cy + r], fill=(0, 0, 0))


def _precip(draw, cx: int, cy: int, r: float, tick: float, color, snow: bool) -> None:
    span = int(r * 1.4)
    for i, dx in enumerate(range(-span, span + 1, 5)):
        phase = (tick * (1.2 if not snow else 0.6) + i * 0.5) % 1.0
        y = cy + int(phase * (r + 4))
        x = cx + dx
        if snow:
            draw.point((x, y), fill=color)
            draw.point((x, y + 1), fill=scale_color(color, 0.6))
        else:
            draw.line([x, y, x, y + 2], fill=color)


def draw_wx_icon(draw, key: str, cx: int, cy: int, r: float, tick: float, day: bool = True) -> None:
    """Draw a weather icon centered at (cx, cy) with radius ~r."""
    if key == "clear":
        _sun(draw, cx, cy, r, tick) if day else _moon(draw, cx, cy, r)
    elif key == "partly":
        if day:
            _sun(draw, int(cx - r * 0.5), int(cy - r * 0.5), r * 0.7, tick)
        else:
            _moon(draw, int(cx - r * 0.5), int(cy - r * 0.5), r * 0.6)
        _cloud(draw, int(cx + r * 0.3), int(cy + r * 0.3), r * 0.8, _CLOUD)
    elif key == "cloud":
        _cloud(draw, cx, cy, r, _CLOUD)
    elif key == "fog":
        _cloud(draw, cx, cy - 1, r * 0.8, _CLOUD_DK)
        for i in range(3):
            yy = cy + r * 0.5 + i * 2
            draw.line([cx - r, yy, cx + r, yy], fill=scale_color(_CLOUD, 0.7))
    elif key == "rain":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD)
        _precip(draw, cx, int(cy + r * 0.5), r, tick, _RAINDROP, snow=False)
    elif key == "snow":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD)
        _precip(draw, cx, int(cy + r * 0.5), r, tick, _SNOW, snow=True)
    elif key == "storm":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD_DK)
        bolt = pulse_color(_BOLT, tick, period=0.5, min_factor=0.4)
        bx, by = cx, int(cy + r * 0.2)
        draw.line([bx + 2, by, bx - 2, by + 4], fill=bolt)
        draw.line([bx - 2, by + 4, bx + 1, by + 4], fill=bolt)
        draw.line([bx + 1, by + 4, bx - 3, by + 9], fill=bolt)
    else:
        _cloud(draw, cx, cy, r, _CLOUD)


def _temp_block(draw, x: int, y: int, value, unit: str, scale: int = 2) -> int:
    """Big temperature number + degree ring + unit letter. Returns right edge x."""
    t = f"{round(value)}"
    draw_big(draw, (x, y), t, fill=WHITE, scale=scale)
    w = big_text_width(t, scale)
    _degree(draw, x + w + 1, y, WHITE)
    draw_micro(draw, (x + w + 1, y + 5), unit[0].upper(), fill=GRAY)
    return x + w + 5


# ── views ────────────────────────────────────────────────────────────────────


def render_current(snap, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    c = snap.current

    draw_micro_centered(draw, 1, _ascii(snap.place)[:16], fill=CYAN)
    draw_wx_icon(draw, c.icon, 15, 24, 8, tick, day=c.is_day)
    _temp_block(draw, 33, 16, c.temp, snap.unit, scale=2)
    draw_micro_centered(draw, 39, c.label, fill=YELLOW)

    hilo = f"H{round(c.high)}  L{round(c.low)}"
    draw_micro_centered(draw, 48, hilo, fill=GRAY)
    extra = f"{c.humidity}% {round(c.wind)}MPH"
    draw_micro_centered(draw, 57, extra, fill=scale_color(CYAN, 0.75))
    return img


def render_forecast(snap, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_micro_centered(draw, 1, _ascii(snap.place)[:16], fill=CYAN)

    days = snap.days[:4]
    if not days:
        draw_micro_centered(draw, 28, "NO DATA", fill=GRAY)
        return img
    colw = WIDTH // 4
    for i, d in enumerate(days):
        x0 = i * colw
        cx = x0 + colw // 2
        label = "TODAY" if i == 0 else d.dow[:3]
        draw_micro_centered(draw, 10, label[:3], fill=WHITE, x0=x0, x1=x0 + colw)
        draw_wx_icon(draw, d.icon, cx, 28, 5, tick, day=True)
        draw_micro_centered(draw, 44, f"{round(d.high)}", fill=YELLOW, x0=x0, x1=x0 + colw)
        draw_micro_centered(draw, 52, f"{round(d.low)}", fill=scale_color(BLUE, 1.1), x0=x0, x1=x0 + colw)
    return img


def render_error(place: str) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_micro_centered(draw, 18, "WEATHER", fill=GRAY)
    draw_micro_centered(draw, 30, _ascii(place)[:16], fill=scale_color(GRAY, 0.8))
    draw_micro_centered(draw, 42, "UNAVAILABLE", fill=scale_color(YELLOW, 0.8))
    return img
