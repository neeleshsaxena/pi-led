"""Visual layout + weather icons for the weather app — UI/UX-owned.

Pure rendering: WeatherSnapshot -> 64x64 frame. Entry points:
    render_current(snap, tick)  -> Image
    render_forecast(snap, tick) -> Image
    render_error(place)         -> Image
See deploy/UI-UX-WORKSTREAM.md for ownership boundaries.

Design notes (same hardware truths as the rest of the panel): bright saturated
colour on true black, no dim full-field fills (they flicker). Temperatures are
shown in **Celsius** regardless of the source unit (converted here), so the
panel reads metric everywhere. Primary number is the big 5x7 font; condition +
hi/lo use the readable 5x7 too; only the tertiary place/humidity line leans on
the 3x5 micro font.
"""
from __future__ import annotations

import math
import unicodedata

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    BLUE,
    CYAN,
    DIM,
    GRAY,
    HEIGHT,
    ORANGE,
    PX_BIG,
    PX_SMALL,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    new_canvas,
    px_cap_height,
    px_text_width,
    pulse_color,
    scale_color,
)

_CLOUD = (165, 178, 202)
_CLOUD_DK = (98, 110, 134)
_SUN = (255, 200, 36)
_SUN_CORE = (255, 234, 130)
_MOON = (216, 226, 250)
_RAINDROP = (74, 165, 255)
_SNOW = (226, 240, 255)
_BOLT = (255, 228, 60)
_HOT = (255, 120, 44)
_COLD = (84, 170, 255)


def _ascii(s: str) -> str:
    norm = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in norm if not unicodedata.combining(c)).upper()


def _to_c(value, unit: str) -> float:
    """Source data may arrive in Fahrenheit (config default) — always show °C."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if str(unit).lower().startswith("f"):
        return (v - 32.0) * 5.0 / 9.0
    return v


def _mph_to_kmh(value) -> float:
    try:
        return float(value) * 1.60934
    except (TypeError, ValueError):
        return 0.0


def _cond_color(icon: str):
    return {
        "clear": YELLOW,
        "partly": YELLOW,
        "cloud": GRAY,
        "fog": GRAY,
        "rain": _COLD,
        "snow": WHITE,
        "storm": ORANGE,
    }.get(icon, GRAY)


# ── weather icons ────────────────────────────────────────────────────────────


def _cloud(draw, cx: int, cy: int, r: float, color) -> None:
    """Puffy cloud centered ~(cx, cy), width ~2r, with a soft lighter cap."""
    s = r
    draw.ellipse([cx - s, cy - s * 0.5, cx - s * 0.1, cy + s * 0.6], fill=color)
    draw.ellipse([cx - s * 0.5, cy - s, cx + s * 0.5, cy + s * 0.4], fill=color)
    draw.ellipse([cx + s * 0.1, cy - s * 0.5, cx + s, cy + s * 0.6], fill=color)
    draw.rectangle([cx - s, cy + s * 0.1, cx + s, cy + s * 0.6], fill=color)
    # lighter highlight along the top puff so it doesn't read as a flat blob
    hi = scale_color(color, 1.25)
    draw.ellipse([cx - s * 0.45, cy - s * 0.95, cx + s * 0.45, cy - s * 0.15], fill=hi)


def _sun(draw, cx: int, cy: int, r: float, tick: float, color=_SUN) -> None:
    rays = scale_color(color, 0.9)
    n = 8
    spin = tick * 0.6
    # rays pulse length slightly so the sun feels alive
    ext = 3 + 1.2 * (0.5 + 0.5 * math.sin(tick * 2.0))
    for i in range(n):
        a = spin + i * (math.tau / n)
        x1, y1 = cx + math.cos(a) * (r + 1), cy + math.sin(a) * (r + 1)
        x2, y2 = cx + math.cos(a) * (r + ext), cy + math.sin(a) * (r + ext)
        draw.line([x1, y1, x2, y2], fill=rays)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    draw.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=_SUN_CORE)


def _moon(draw, cx: int, cy: int, r: float, tick: float = 0.0) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_MOON)
    off = r * 0.55
    draw.ellipse([cx - r + off, cy - r - 1, cx + r + off, cy + r + 1], fill=(0, 0, 0))
    # a twinkling star beside the crescent
    tw = pulse_color(WHITE, tick, period=1.3, min_factor=0.3)
    sx, sy = int(cx + r * 0.9), int(cy - r * 0.9)
    draw.point((sx, sy), fill=tw)
    draw.point((sx - 1, sy), fill=scale_color(tw, 0.5))
    draw.point((sx + 1, sy), fill=scale_color(tw, 0.5))
    draw.point((sx, sy - 1), fill=scale_color(tw, 0.5))
    draw.point((sx, sy + 1), fill=scale_color(tw, 0.5))


def _precip(draw, cx: int, cy: int, r: float, tick: float, color, snow: bool) -> None:
    span = int(r * 1.4)
    for i, dx in enumerate(range(-span, span + 1, 4)):
        phase = (tick * (0.9 if snow else 1.6) + i * 0.37) % 1.0
        y = cy + int(phase * (r + 5))
        x = cx + dx
        if snow:
            f = pulse_color(color, tick + i, period=1.0, min_factor=0.5)
            draw.point((x, y), fill=f)
            draw.point((x, y + 1), fill=scale_color(f, 0.55))
        else:
            # slanted streak so rain reads as motion
            draw.line([x, y, x - 1, y + 3], fill=color)


def draw_wx_icon(draw, key: str, cx: int, cy: int, r: float, tick: float, day: bool = True) -> None:
    """Draw a weather icon centered at (cx, cy) with radius ~r."""
    if key == "clear":
        _sun(draw, cx, cy, r, tick) if day else _moon(draw, cx, cy, r, tick)
    elif key == "partly":
        if day:
            _sun(draw, int(cx - r * 0.5), int(cy - r * 0.5), r * 0.7, tick)
        else:
            _moon(draw, int(cx - r * 0.5), int(cy - r * 0.5), r * 0.6, tick)
        _cloud(draw, int(cx + r * 0.3), int(cy + r * 0.35), r * 0.8, _CLOUD)
    elif key == "cloud":
        _cloud(draw, int(cx - r * 0.25), int(cy - r * 0.15), r * 0.7, _CLOUD_DK)
        _cloud(draw, int(cx + r * 0.15), int(cy + r * 0.15), r * 0.85, _CLOUD)
    elif key == "fog":
        _cloud(draw, cx, cy - 1, r * 0.8, _CLOUD_DK)
        for i in range(3):
            yy = cy + r * 0.5 + i * 2
            drift = math.sin(tick * 1.2 + i) * 2
            draw.line([cx - r + drift, yy, cx + r + drift, yy], fill=scale_color(_CLOUD, 0.7))
    elif key == "rain":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD)
        _precip(draw, cx, int(cy + r * 0.5), r, tick, _RAINDROP, snow=False)
    elif key == "snow":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD)
        _precip(draw, cx, int(cy + r * 0.5), r, tick, _SNOW, snow=True)
    elif key == "storm":
        _cloud(draw, cx, cy - r * 0.4, r, _CLOUD_DK)
        _precip(draw, cx, int(cy + r * 0.5), r, tick, _RAINDROP, snow=False)
        bolt = pulse_color(_BOLT, tick, period=0.5, min_factor=0.35)
        bx, by = cx, int(cy + r * 0.1)
        draw.line([bx + 2, by, bx - 2, by + 4], fill=bolt)
        draw.line([bx - 2, by + 4, bx + 1, by + 4], fill=bolt)
        draw.line([bx + 1, by + 4, bx - 3, by + 9], fill=bolt)
    else:
        _cloud(draw, cx, cy, r, _CLOUD)


# ── small text helpers ────────────────────────────────────────────────────────


def _draw_segments_centered(draw, y: int, segments, size: int = PX_SMALL, gap: int = 4) -> None:
    """Draw a row of (text, color) chunks centered as one group — lets a single
    line mix colours (e.g. a warm high and a cool low)."""
    total = sum(px_text_width(t, size) for t, _ in segments) + gap * (len(segments) - 1)
    x = (WIDTH - total) // 2
    for t, col in segments:
        draw_px(draw, (x, y), t, fill=col, size=size)
        x += px_text_width(t, size) + gap


# ── views ────────────────────────────────────────────────────────────────────


def render_current(snap, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    c = snap.current

    # place name (small caps, cyan)
    draw_px_centered(draw, 1, _ascii(snap.place)[:14], fill=CYAN, size=PX_SMALL)

    # hero row: animated icon (left) + big temperature.
    # (kenpixel's ° glyph is a filled block at this size, so draw a crisp ring.)
    draw_wx_icon(draw, c.icon, 12, 26, 9, tick, day=c.is_day)
    temp = f"{round(_to_c(c.temp, snap.unit))}"
    ty = 18
    draw_px(draw, (27, ty), temp, fill=WHITE, size=PX_BIG)
    ux = 27 + px_text_width(temp, PX_BIG) + 2
    draw.ellipse([ux, ty + 1, ux + 3, ty + 4], outline=WHITE)  # degree ring
    cy = ty + (px_cap_height(PX_BIG) - px_cap_height(PX_SMALL))  # bottom-align 'C'
    draw_px(draw, (ux, cy), "C", fill=CYAN, size=PX_SMALL)

    # condition label — kenpixel, condition-tinted
    label = _ascii(c.label)
    while label and px_text_width(label, PX_SMALL) > WIDTH - 2:
        label = label[:-1]
    draw_px_centered(draw, 40, label, fill=_cond_color(c.icon), size=PX_SMALL)

    # hi / lo — warm high, cool low, on one centered line
    hi = f"{round(_to_c(c.high, snap.unit))}"
    lo = f"{round(_to_c(c.low, snap.unit))}"
    _draw_segments_centered(draw, 49, [(f"H{hi}", _HOT), (f"L{lo}", _COLD)], size=PX_SMALL, gap=5)

    # humidity + wind (km/h) — tertiary line, muted
    extra = f"{c.humidity}%  {round(_mph_to_kmh(c.wind))}KM/H"
    draw_px_centered(draw, 57, extra, fill=scale_color(CYAN, 0.7), size=PX_SMALL)
    return img


def render_forecast(snap, tick: float) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 0, _ascii(snap.place)[:14], fill=CYAN, size=PX_SMALL)

    days = snap.days[:4]
    if not days:
        draw_px_centered(draw, 28, "NO DATA", fill=GRAY, size=PX_SMALL)
        return img

    colw = WIDTH // 4
    for i, d in enumerate(days):
        x0 = i * colw
        cx = x0 + colw // 2
        # thin column separators (subtle structure, still visible when lit)
        if i > 0:
            draw.line([(x0, 10), (x0, HEIGHT - 3)], fill=DIM)

        is_today = i == 0
        # day labels stay in the micro font — kenpixel is too wide for a 16px column
        draw_micro_centered(draw, 11, d.dow[:3], fill=YELLOW if is_today else GRAY,
                            x0=x0, x1=x0 + colw)
        draw_wx_icon(draw, d.icon, cx, 28, 5, tick, day=True)

        hi = f"{round(_to_c(d.high, snap.unit))}"
        lo = f"{round(_to_c(d.low, snap.unit))}"
        draw_px_centered(draw, 41, hi, fill=_HOT, size=PX_SMALL, x0=x0, x1=x0 + colw)
        draw_px_centered(draw, 51, lo, fill=_COLD, size=PX_SMALL, x0=x0, x1=x0 + colw)
    return img


def render_error(place: str) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 16, "WEATHER", fill=GRAY, size=PX_SMALL)
    draw_px_centered(draw, 30, _ascii(place)[:14], fill=scale_color(GRAY, 0.8), size=PX_SMALL)
    draw_px_centered(draw, 42, "UNAVAILABLE", fill=scale_color(YELLOW, 0.8), size=PX_SMALL)
    return img
