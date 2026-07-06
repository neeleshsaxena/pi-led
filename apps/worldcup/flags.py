"""Pixel flags for the World Cup knockout tour.

Each `_sq_*(s)` draws an s×s RGB square flag (designed to read well around 24-28px
but scales down too). `flag_badge(abbr, s)` crops it to a circle with a light ring
— the poster look. Unknown teams fall back to a two-tone split from the team's
colors (teams.colors_for), so any team renders even without a hand-drawn flag.

Flags are impressionistic at panel scale: dominant fields / stripes / crosses read
clearly; emblems are hinted, not literal.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from .teams import colors_for

# Flag palette (slightly punchy so it reads on the LED panel).
RED = (206, 43, 55)
WHITE = (238, 238, 240)
BLUE = (36, 64, 142)
NAVY = (18, 36, 94)
BLACK = (26, 26, 28)
YELLOW = (255, 206, 42)
GREEN = (28, 138, 74)
SKY = (110, 178, 224)
GOLD = (214, 170, 78)
RING = (224, 224, 230)


def _bands(s, spec, vertical=True):
    """Colored bands. spec = [(color, weight), ...]."""
    img = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(img)
    tot = sum(w for _, w in spec)
    acc = 0
    for c, w in spec:
        a = round(acc * s / tot)
        acc += w
        b = round(acc * s / tot) - 1
        if vertical:
            d.rectangle([a, 0, b, s - 1], fill=c)
        else:
            d.rectangle([0, a, s - 1, b], fill=c)
    return img


def _star(d, cx, cy, r, color, points=5, rot=-90.0):
    pts = []
    for i in range(points * 2):
        ang = math.radians(rot + i * 180.0 / points)
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    d.polygon(pts, fill=color)


def _dot(d, cx, cy, r, color):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


# ── vertical tricolors ────────────────────────────────────────────────────────
def _fra(s):
    return _bands(s, [(BLUE, 1), (WHITE, 1), (RED, 1)])


def _bel(s):
    return _bands(s, [(BLACK, 1), (YELLOW, 1), (RED, 1)])


def _mex(s):
    img = _bands(s, [(GREEN, 1), (WHITE, 1), (RED, 1)])
    _dot(ImageDraw.Draw(img), s / 2, s / 2, max(1, s * 0.09), (120, 82, 52))  # emblem hint
    return img


def _can(s):
    img = _bands(s, [(RED, 1), (WHITE, 2), (RED, 1)])
    d = ImageDraw.Draw(img)
    cx = cy = (s - 1) / 2
    r = s * 0.22
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=RED)  # leaf hint (diamond)
    return img


# ── horizontal tricolors ──────────────────────────────────────────────────────
def _par(s):
    img = _bands(s, [(RED, 1), (WHITE, 1), (BLUE, 1)], vertical=False)
    _dot(ImageDraw.Draw(img), s / 2, s / 2, max(1, s * 0.08), (70, 128, 70))
    return img


def _ned(s):
    return _bands(s, [(RED, 1), (WHITE, 1), (BLUE, 1)], vertical=False)


def _arg(s):
    img = _bands(s, [(SKY, 1), (WHITE, 1), (SKY, 1)], vertical=False)
    _dot(ImageDraw.Draw(img), s / 2, s / 2, max(1, s * 0.13), (232, 182, 54))  # sun
    return img


def _egy(s):
    img = _bands(s, [(RED, 1), (WHITE, 1), (BLACK, 1)], vertical=False)
    _dot(ImageDraw.Draw(img), s / 2, s / 2, max(1, s * 0.09), GOLD)  # eagle hint
    return img


def _col(s):
    return _bands(s, [(YELLOW, 2), (BLUE, 1), (RED, 1)], vertical=False)


def _esp(s):
    img = _bands(s, [(RED, 1), (YELLOW, 2), (RED, 1)], vertical=False)
    d = ImageDraw.Draw(img)
    d.rectangle([round(s * 0.30), s // 2 - 2, round(s * 0.30) + 2, s // 2 + 2], fill=(168, 60, 50))
    return img


def _por(s):
    img = _bands(s, [(GREEN, 2), (RED, 3)])
    d = ImageDraw.Draw(img)
    bx = round(2 * s / 5)
    _dot(d, bx, s / 2, max(1, s * 0.11), YELLOW)
    _dot(d, bx, s / 2, max(1, s * 0.05), (180, 40, 40))
    return img


# ── special constructions ─────────────────────────────────────────────────────
def _bra(s):
    img = Image.new("RGB", (s, s), GREEN)
    d = ImageDraw.Draw(img)
    cx = cy = (s - 1) / 2
    r = s * 0.44
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=YELLOW)  # diamond
    br = max(2, s * 0.20)
    _dot(d, cx, cy, br, NAVY)  # blue disc
    d.line([(cx - br, cy + 1), (cx + br, cy - 1)], fill=WHITE)  # band hint
    return img


def _nor(s):
    img = Image.new("RGB", (s, s), RED)
    d = ImageDraw.Draw(img)
    vx = round(s * 0.40)
    c = (s - 1) // 2
    wf = max(1, round(s * 0.20))
    bf = max(1, round(s * 0.09))
    d.rectangle([vx - wf, 0, vx + wf, s - 1], fill=WHITE)
    d.rectangle([0, c - wf, s - 1, c + wf], fill=WHITE)
    d.rectangle([vx - bf, 0, vx + bf, s - 1], fill=NAVY)
    d.rectangle([0, c - bf, s - 1, c + bf], fill=NAVY)
    return img


def _eng(s):
    img = Image.new("RGB", (s, s), WHITE)
    d = ImageDraw.Draw(img)
    c = (s - 1) // 2
    hw = max(1, round(s * 0.13))
    d.rectangle([c - hw, 0, c + hw, s - 1], fill=RED)
    d.rectangle([0, c - hw, s - 1, c + hw], fill=RED)
    return img


def _sui(s):
    img = Image.new("RGB", (s, s), RED)
    d = ImageDraw.Draw(img)
    c = (s - 1) // 2
    hw = max(1, round(s * 0.12))
    arm = round(s * 0.28)
    d.rectangle([c - hw, c - arm, c + hw, c + arm], fill=WHITE)
    d.rectangle([c - arm, c - hw, c + arm, c + hw], fill=WHITE)
    return img


def _mar(s):
    img = Image.new("RGB", (s, s), RED)
    _star(ImageDraw.Draw(img), (s - 1) / 2, (s - 1) / 2, s * 0.30, GREEN, points=5)
    return img


def _usa(s):
    img = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(img)
    n = 7
    for y in range(s):
        d.line([(0, y), (s - 1, y)], fill=RED if (y * n // s) % 2 == 0 else WHITE)
    cw = round(s * 0.46)
    ch = round(s * 0.54)
    d.rectangle([0, 0, cw - 1, ch - 1], fill=NAVY)
    for yy in range(2, ch - 1, 3):
        for xx in range(1, cw - 1, 3):
            d.point((xx, yy), fill=WHITE)
    return img


_FLAGS = {
    "PAR": _par, "FRA": _fra, "CAN": _can, "MAR": _mar, "POR": _por, "ESP": _esp,
    "USA": _usa, "BEL": _bel, "BRA": _bra, "NOR": _nor, "MEX": _mex, "ENG": _eng,
    "ARG": _arg, "EGY": _egy, "SUI": _sui, "COL": _col, "NED": _ned,
}


def has_flag(abbr: str) -> bool:
    return (abbr or "").strip().upper() in _FLAGS


def flag_square(abbr: str, s: int) -> Image.Image:
    ab = (abbr or "").strip().upper()
    fn = _FLAGS.get(ab)
    if fn:
        return fn(s)
    # Fallback: two-tone diagonal split from the team's colors.
    primary, secondary = colors_for(ab)
    img = Image.new("RGB", (s, s), primary)
    ImageDraw.Draw(img).polygon([(0, 0), (s, 0), (0, s)], fill=secondary)
    return img


def flag_badge(abbr: str, s: int, ring=RING) -> Image.Image:
    """Circular flag badge (RGBA) with a thin light ring — the poster look."""
    sq = flag_square(abbr, s).convert("RGBA")
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=255)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(sq, (0, 0), mask)
    if ring:
        ImageDraw.Draw(out).ellipse([0, 0, s - 1, s - 1], outline=ring)
    return out
