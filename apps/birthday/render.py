"""Birthday countdown — pixel rendering.

Three scenes that escalate as the day approaches:
  - countdown  (>1 day): big "N DAYS", bobbing balloons, soft sparkles.
  - final      (last 24h): live HH:MM:SS, chasing marquee border, confetti.
  - celebration(the day): "HAPPY BIRTHDAY <name>!" scroll, fireworks + confetti +
                          rising balloons + rainbow marquee.

Pure rendering: given (name, days, remaining_seconds, tick) produce one 64x64
frame. Animation is derived from `tick` (mostly stateless / seeded), so no
per-frame state is kept here.
"""
from __future__ import annotations

import math
import random

from PIL import ImageDraw

from pi_led_core.canvas import (
    CYAN,
    GRAY,
    GREEN,
    HEIGHT,
    ORANGE,
    PURPLE,
    PX_BIG,
    PX_HUGE,
    PX_SMALL,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    hsv_color,
    new_canvas,
    pulse_color,
    px_text_width,
    rainbow,
    scale_color,
    sparkle,
)

PINK = (255, 95, 165)
GOLD = (255, 200, 64)
_PARTY = [PINK, GOLD, CYAN, GREEN, PURPLE, ORANGE, WHITE]


# ── particles / decor (stateless, tick-driven) ───────────────────────────────
def _confetti(img, tick, count=22, speed=11.0) -> None:
    """Colored flakes drifting down, wobbling. Deterministic per flake."""
    d = ImageDraw.Draw(img)
    for i in range(count):
        rnd = random.Random(i * 7 + 3)
        x0 = rnd.randint(0, WIDTH - 1)
        col = _PARTY[i % len(_PARTY)]
        phase = rnd.random() * 100.0
        drift = rnd.uniform(0.7, 1.4)
        y = int((tick * speed * drift + phase * 13) % (HEIGHT + 6)) - 3
        x = int(x0 + 3.0 * math.sin(tick * 2.0 + phase)) % WIDTH
        d.rectangle([x, y, x + 1, y + 1], fill=col)


def _balloon(draw, cx, cy, color) -> None:
    """A little balloon: rounded body + highlight + string."""
    draw.ellipse([cx - 3, cy - 4, cx + 3, cy + 4], fill=color)
    draw.point((cx - 1, cy - 2), fill=scale_color(WHITE, 0.9))  # sheen
    draw.polygon([(cx - 1, cy + 4), (cx + 1, cy + 4), (cx, cy + 5)], fill=scale_color(color, 0.7))  # knot
    for k in range(1, 6):  # squiggly string
        draw.point((cx + (k % 2), cy + 5 + k), fill=scale_color(GRAY, 0.6))


def _marquee(draw, tick, color=GOLD, speed=11.0) -> None:
    """Chasing lights around the border (cinema-sign vibe)."""
    step = 4
    perim = []
    perim += [(x, 0) for x in range(0, WIDTH, step)]
    perim += [(WIDTH - 1, y) for y in range(0, HEIGHT, step)]
    perim += [(x, HEIGHT - 1) for x in range(WIDTH - 1, 0, -step)]
    perim += [(0, y) for y in range(HEIGHT - 1, 0, -step)]
    n = len(perim)
    head = int(tick * speed) % n
    for i, (px, py) in enumerate(perim):
        d = (i - head) % n
        b = 1.0 if d < 3 else 0.18
        draw.point((px, py), fill=scale_color(color, b))


def _fireworks(draw, tick) -> None:
    """A few overlapping bursts: each expands from a point and fades."""
    for k in range(3):
        rnd = random.Random(k * 17 + 5)
        period = rnd.uniform(2.2, 3.6)
        phase = (tick + rnd.random() * period) % period
        if phase > 1.3:
            continue
        cx = rnd.randint(12, WIDTH - 12)
        cy = rnd.randint(8, 32)
        col = hsv_color((tick * 0.13 + k * 0.33) % 1.0, 0.85, 1.0)
        r = phase * 17.0
        fade = max(0.0, 1.0 - phase / 1.3)
        for a in range(0, 360, 24):
            ang = math.radians(a)
            x = int(cx + math.cos(ang) * r)
            y = int(cy + math.sin(ang) * r)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                draw.point((x, y), fill=scale_color(col, fade))


def _rising_balloons(draw, tick, count=4) -> None:
    for k in range(count):
        rnd = random.Random(k * 9 + 11)
        bx = rnd.randint(6, WIDTH - 6)
        col = _PARTY[k % len(_PARTY)]
        span = HEIGHT + 18
        by = HEIGHT + 6 - int((tick * 9.0 + rnd.random() * span) % span)
        if -6 < by < HEIGHT + 6:
            _balloon(draw, bx, by, col)


# ── scenes ───────────────────────────────────────────────────────────────────
def _countdown(name, days, tick):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, name, fill=PINK, size=PX_SMALL)
    draw_micro_centered(draw, 9, "BIRTHDAY IN", fill=scale_color(GOLD, 0.9))
    _balloon(draw, 7, 30, PINK)
    _balloon(draw, WIDTH - 8, 33, CYAN)
    num = str(days)
    size = PX_HUGE if len(num) == 1 else PX_BIG
    ny = 18 if len(num) == 1 else 21
    draw_px_centered(draw, ny, num, fill=pulse_color(GOLD, tick, period=2.0, min_factor=0.7), size=size)
    draw_px_centered(draw, 46, "DAYS" if days != 1 else "DAY", fill=WHITE, size=PX_SMALL)
    sparkle(draw, tick, count=9, seed=4)
    return img


def _final(name, remaining, tick):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    _marquee(draw, tick, color=GOLD)
    _confetti(img, tick, count=16, speed=13.0)
    h = int(remaining // 3600)
    m = int((remaining % 3600) // 60)
    s = int(remaining % 60)
    draw_px_centered(draw, 5, "ALMOST!", fill=pulse_color(PINK, tick, period=1.2, min_factor=0.6), size=PX_SMALL)
    draw_px_centered(draw, 24, f"{h:02d}:{m:02d}:{s:02d}", fill=WHITE, size=PX_BIG)
    draw_micro_centered(draw, 46, f"TIL {name}'S DAY", fill=CYAN)
    return img


def _scroll(img, text, y, tick, color, speed=16.0) -> None:
    d = ImageDraw.Draw(img)
    tw = px_text_width(text, PX_SMALL)
    total = tw + WIDTH
    x = WIDTH - int((tick * speed) % total)
    draw_px(d, (x, y), text, fill=color, size=PX_SMALL)


def _celebration(name, tick):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    _fireworks(draw, tick)
    _rising_balloons(draw, tick, count=4)
    _confetti(img, tick, count=24, speed=15.0)
    _marquee(draw, tick, color=rainbow(tick, period=2.2), speed=14.0)
    # readable banner band behind the scrolling greeting
    filled_rect(draw, 0, 26, WIDTH - 1, 36, (10, 10, 14))
    _scroll(img, f"HAPPY BIRTHDAY {name}!   ", 28, tick, rainbow(tick, period=1.3), speed=17.0)
    return img


def render_birthday(name, days, remaining, tick=0.0):
    name = (name or "").upper()
    if days <= 0:
        return _celebration(name, tick)
    if days == 1:
        return _final(name, remaining, tick)
    return _countdown(name, days, tick)
