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


def _bob(cy: int, tick: float, phase: float = 0.0, amp: float = 2.0) -> int:
    """Gentle float for a balloon — smooth, never leaves the panel."""
    return int(round(cy + amp * math.sin(tick * 1.5 + phase)))


def _cake(draw, cx: int, cy: int, tick: float, candles: int = 3) -> None:
    """Layer cake with flickering candles. (cx, cy) = center of the frosting line;
    the cake occupies roughly cy-8 (flames) .. cy+8 (plate)."""
    w = 15
    x0, x1 = cx - w // 2, cx + w // 2
    gap = w // (candles + 1)
    for i in range(candles):
        px_ = x0 + gap * (i + 1)
        draw.line([(px_, cy - 6), (px_, cy - 2)], fill=(255, 246, 224))       # candle
        flame = pulse_color(YELLOW, tick + i * 0.7, period=0.5, min_factor=0.6)
        draw.point((px_, cy - 8), fill=flame)                                  # flame tip
        draw.point((px_, cy - 7), fill=scale_color(ORANGE, 0.95))              # flame base
    filled_rect(draw, x0, cy - 1, x1, cy + 1, (255, 240, 250))                 # frosting
    filled_rect(draw, x0, cy + 2, x1, cy + 7, PINK)                            # body
    for i in range(x0 + 1, x1, 3):                                             # sprinkles
        draw.point((i, cy + 4), fill=_PARTY[i % len(_PARTY)])
    filled_rect(draw, x0 - 2, cy + 8, x1 + 2, cy + 8, scale_color(CYAN, 0.85))  # plate


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
    # balloons actually bob now (offset phases so they don't move in lockstep)
    _balloon(draw, 7, _bob(28, tick, 0.0), PINK)
    _balloon(draw, WIDTH - 8, _bob(30, tick, 1.9), CYAN)
    num = str(days)
    one = len(num) == 1
    size = PX_HUGE if one else PX_BIG
    ny = 15 if one else 21
    draw_px_centered(draw, ny, num, fill=pulse_color(GOLD, tick, period=2.0, min_factor=0.7), size=size)
    draw_px_centered(draw, 38, "DAYS" if days != 1 else "DAY", fill=WHITE, size=PX_SMALL)
    _cake(draw, WIDTH // 2, 54, tick)
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
    # HH:MM:SS at PX_BIG is ~96px — far wider than the 64px panel (it used to be
    # clipped at both edges). Big HH:MM reads as the hero; seconds tick beneath.
    draw_px_centered(draw, 17, f"{h:02d}:{m:02d}", fill=WHITE, size=PX_BIG)
    draw_px_centered(draw, 34, f"{s:02d}", fill=pulse_color(GOLD, tick, period=1.0, min_factor=0.65), size=PX_SMALL)
    draw_micro_centered(draw, 45, f"TIL {name}'S DAY", fill=CYAN)
    # how far through the final day we are — fills as midnight approaches
    frac = max(0.0, min(1.0, 1.0 - remaining / 86400.0))
    filled_rect(draw, 6, 54, WIDTH - 7, 54, scale_color(GRAY, 0.35))
    end = 6 + int(frac * (WIDTH - 13))
    if end > 6:
        filled_rect(draw, 6, 54, end, 54, GOLD)
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
    # Readable banner behind the scrolling greeting. TRUE black, not a dim wash —
    # partial-brightness fills visibly flicker on this HUB75 panel. Bright rules
    # above/below frame the band instead of relying on a lifted background.
    filled_rect(draw, 0, 25, WIDTH - 1, 37, (0, 0, 0))
    rule = rainbow(tick, period=2.2)
    filled_rect(draw, 0, 24, WIDTH - 1, 24, rule)
    filled_rect(draw, 0, 38, WIDTH - 1, 38, rule)
    _scroll(img, f"HAPPY BIRTHDAY {name}!   ", 28, tick, rainbow(tick, period=1.3), speed=17.0)
    return img


def render_milestone(name, months, is_day=False, tick=0.0):
    """Monthly milestone card — "<NAME> / N / MONTHS" over a candle-lit cake, with
    confetti + a marquee. On the milestone day itself it goes full party (rainbow
    marquee + fireworks); other days it's a calmer 'you are N months old' card."""
    name = (name or "").upper()
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    _marquee(draw, tick, color=rainbow(tick, period=2.4) if is_day else GOLD, speed=9.0)
    _confetti(img, tick, count=18 if is_day else 9, speed=10.0)
    if is_day:
        _fireworks(draw, tick)
    draw_px_centered(draw, 2, name, fill=PINK, size=PX_SMALL)
    num = str(max(0, int(months)))
    draw_px_centered(
        draw, 12, num,
        fill=pulse_color(GOLD, tick, period=2.0, min_factor=0.7),
        size=PX_HUGE if len(num) == 1 else PX_BIG,
    )
    draw_px_centered(draw, 33, "MONTHS" if months != 1 else "MONTH", fill=WHITE, size=PX_SMALL)
    _cake(draw, WIDTH // 2, 52, tick, candles=max(1, min(int(months) or 1, 4)))
    sparkle(draw, tick, count=8, seed=6)
    return img


def render_birthday(name, days, remaining, tick=0.0):
    name = (name or "").upper()
    if days <= 0:
        return _celebration(name, tick)
    if days == 1:
        return _final(name, remaining, tick)
    return _countdown(name, days, tick)
