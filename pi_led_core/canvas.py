from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

WIDTH = 64
HEIGHT = 64

BLACK = (0, 0, 0)
# Punchy palette: the HUB75 panel has a blown-out, saturated response and runs
# dim, so push values high and avoid muddy mid-grays. Tuned for "pops from
# across the room" over print-accurate.
WHITE = (255, 255, 255)
GRAY = (140, 150, 170)   # cool light gray — reads clearly, not muddy
DIM = (70, 78, 95)       # subtle structure (dividers), still visible when lit
RED = (255, 48, 48)
GREEN = (32, 240, 96)
YELLOW = (255, 215, 32)
ORANGE = (255, 140, 24)
BLUE = (64, 150, 255)
CYAN = (32, 230, 230)
MAGENTA = (255, 56, 180)
PINK = (255, 96, 160)
PURPLE = (170, 96, 255)
LIME = (170, 255, 48)
ACCENT = ORANGE

_font_cache: dict[str, ImageFont.ImageFont] = {}


def font_small() -> ImageFont.ImageFont:
    if "small" not in _font_cache:
        _font_cache["small"] = ImageFont.load_default()
    return _font_cache["small"]


def new_canvas(bg: tuple[int, int, int] = BLACK) -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), bg)


def text_width(draw: ImageDraw.ImageDraw, text: str, font=None) -> int:
    bbox = draw.textbbox((0, 0), text, font=font or font_small())
    return bbox[2] - bbox[0]


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int] = WHITE,
    font=None,
) -> None:
    draw.text(xy, text, fill=fill, font=font or font_small())


def draw_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    fill: tuple[int, int, int] = WHITE,
    font=None,
) -> None:
    f = font or font_small()
    w = text_width(draw, text, f)
    draw.text(((WIDTH - w) // 2, y), text, fill=fill, font=f)


def draw_hline(
    draw: ImageDraw.ImageDraw,
    y: int,
    fill: tuple[int, int, int] = DIM,
    x0: int = 0,
    x1: int = WIDTH,
) -> None:
    draw.line([(x0, y), (x1 - 1, y)], fill=fill)


def filled_rect(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    fill: tuple[int, int, int],
) -> None:
    draw.rectangle([x0, y0, x1, y1], fill=fill)


# ─── color helpers ───────────────────────────────────────────────────────────


def scale_color(c: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Multiply each channel by `factor`, clamped to 0-255."""
    return (
        max(0, min(255, int(c[0] * factor))),
        max(0, min(255, int(c[1] * factor))),
        max(0, min(255, int(c[2] * factor))),
    )


def lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linearly interpolate between c1 and c2; t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def pulse_color(
    base: tuple[int, int, int],
    tick: float,
    period: float = 1.2,
    min_factor: float = 0.55,
    max_factor: float = 1.0,
) -> tuple[int, int, int]:
    """Modulate `base` brightness over time. tick = monotonic seconds.

    Default `min_factor` keeps animated elements well above black so a "breathing"
    pulse never reads as a flicker/blink on the PWM panel. Prefer this over
    toggling pixels on/off for motion.
    """
    import math
    phase = (math.sin(tick / period * math.tau) + 1) / 2  # 0..1
    factor = min_factor + (max_factor - min_factor) * phase
    return scale_color(base, factor)


# ─── vivid effects: hue, gradients, glow, sparkle ────────────────────────────


def hsv_color(h: float, s: float = 1.0, v: float = 1.0) -> tuple[int, int, int]:
    """HSV → RGB. h wraps (any float, 1.0 = full circle). Great for rainbows."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (int(r * 255), int(g * 255), int(b * 255))


def rainbow(tick: float, offset: float = 0.0, period: float = 6.0, s: float = 1.0, v: float = 1.0):
    """A smoothly cycling rainbow color driven by time."""
    return hsv_color(tick / period + offset, s, v)


def fill_vgradient(
    img: Image.Image,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    y0: int = 0,
    y1: int = HEIGHT,
) -> None:
    """Paint a vertical gradient between y0 and y1 (in place)."""
    draw = ImageDraw.Draw(img)
    span = max(1, y1 - 1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / span
        draw.line([(0, y), (WIDTH - 1, y)], fill=lerp_color(top, bottom, t))


def fill_split_tint(
    img: Image.Image,
    left: tuple[int, int, int],
    right: tuple[int, int, int],
    factor: float = 0.16,
) -> None:
    """Dim two-color wash: left half tinted `left`, right half `right`, blended
    across the middle. Keeps text legible while giving the frame a colored
    identity (e.g. the two teams' colors)."""
    draw = ImageDraw.Draw(img)
    half = WIDTH / 2
    for x in range(WIDTH):
        t = max(0.0, min(1.0, (x - half * 0.5) / half))
        c = lerp_color(scale_color(left, factor), scale_color(right, factor), t)
        draw.line([(x, 0), (x, HEIGHT - 1)], fill=c)


def draw_big_glow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int] = WHITE,
    glow: tuple[int, int, int] | None = None,
    scale: int = 2,
    spacing: int = 1,
    glow_factor: float = 0.5,
) -> None:
    """Draw big text with a soft 1px colored halo so it 'blooms' like real LEDs."""
    x0, y0 = xy
    g = scale_color(glow if glow is not None else fill, glow_factor)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw_big(draw, (x0 + dx, y0 + dy), text, fill=g, scale=scale, spacing=spacing)
    draw_big(draw, (x0, y0), text, fill=fill, scale=scale, spacing=spacing)


def draw_big_glow_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    fill: tuple[int, int, int] = WHITE,
    glow: tuple[int, int, int] | None = None,
    scale: int = 2,
    spacing: int = 1,
    glow_factor: float = 0.5,
) -> None:
    w = big_text_width(text, scale, spacing)
    x = (WIDTH - w) // 2
    draw_big_glow(draw, (x, y), text, fill=fill, glow=glow, scale=scale,
                  spacing=spacing, glow_factor=glow_factor)


def sparkle(
    draw: ImageDraw.ImageDraw,
    tick: float,
    count: int = 14,
    seed: int = 0,
    colors: tuple = None,
    box: tuple[int, int, int, int] = (0, 0, WIDTH, HEIGHT),
) -> None:
    """Twinkling confetti — pseudo-random points that fade in/out on their own
    phase. Cheap celebratory effect for goals / attract screens."""
    import math
    import random
    cols = colors or (WHITE, YELLOW, CYAN, MAGENTA, GREEN)
    x0, y0, x1, y1 = box
    rng = random.Random(seed)
    for i in range(count):
        px = rng.randint(x0, x1 - 1)
        py = rng.randint(y0, y1 - 1)
        phase = rng.random()
        speed = 0.6 + rng.random() * 1.6
        b = (math.sin((tick * speed + phase) * math.tau) + 1) / 2
        if b < 0.25:
            continue
        c = scale_color(cols[i % len(cols)], b)
        draw.point((px, py), fill=c)


def sweep_vbar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y0: int,
    y1: int,
    color: tuple[int, int, int],
    tick: float,
    period: float = 2.6,
    band: float = 7.0,
    hi: float = 0.85,
) -> None:
    """A solid vertical bar in `color` with a bright highlight band gliding down
    it. Always >= the base color (flicker-safe); adds life to team edge bars."""
    h = y1 - y0 + 1
    center = ((tick / period) % 1.0) * (h + band) - band / 2.0
    half = band / 2.0
    for i in range(h):
        t = 1.0 - min(1.0, abs(i - center) / half)
        c = lerp_color(color, WHITE, hi * t) if t > 0 else color
        draw.point((x, y0 + i), fill=c)


def sweep_hbar(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    color: tuple[int, int, int],
    tick: float,
    period: float = 2.6,
    band: float = 11.0,
    hi: float = 0.85,
) -> None:
    """Horizontal twin of `sweep_vbar` — a highlight glides left→right along a
    `color` rule (e.g. a header accent line)."""
    w = x1 - x0 + 1
    center = ((tick / period) % 1.0) * (w + band) - band / 2.0
    half = band / 2.0
    for i in range(w):
        t = 1.0 - min(1.0, abs(i - center) / half)
        c = lerp_color(color, WHITE, hi * t) if t > 0 else color
        draw.point((x0 + i, y), fill=c)


# ─── 5x7 pixel digits for "big score" rendering ──────────────────────────────
# Width 5, height 7. '#' = on, '.' = off.

_GLYPHS_5x7 = {
    # Digits
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "#.#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    # Uppercase letters
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#..##", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#...#", "#.#.#", "##.##", "#...#"],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    # Punctuation / symbols
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    ":": [".....", ".....", "..#..", ".....", "..#..", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", ".##.."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "'": [".#...", ".#...", "#....", ".....", ".....", ".....", "....."],
    "+": [".....", ".....", "..#..", ".###.", "..#..", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
}

GLYPH_W = 5
GLYPH_H = 7


def big_text_width(text: str, scale: int = 1, spacing: int = 1) -> int:
    if not text:
        return 0
    return len(text) * (GLYPH_W * scale + spacing) - spacing


def draw_big(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int] = WHITE,
    scale: int = 2,
    spacing: int = 1,
) -> None:
    """Render `text` using 5x7 pixel glyphs scaled up by `scale`."""
    x0, y0 = xy
    for ch in text:
        glyph = _GLYPHS_5x7.get(ch) or _GLYPHS_5x7[" "]
        for ry, row in enumerate(glyph):
            for cx, pixel in enumerate(row):
                if pixel == "#":
                    px = x0 + cx * scale
                    py = y0 + ry * scale
                    if scale == 1:
                        draw.point((px, py), fill=fill)
                    else:
                        draw.rectangle([px, py, px + scale - 1, py + scale - 1], fill=fill)
        x0 += GLYPH_W * scale + spacing


def draw_big_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    fill: tuple[int, int, int] = WHITE,
    scale: int = 2,
    spacing: int = 1,
) -> None:
    w = big_text_width(text, scale, spacing)
    x = (WIDTH - w) // 2
    draw_big(draw, (x, y), text, fill=fill, scale=scale, spacing=spacing)


# ─── 3x5 micro font for crisp small labels ───────────────────────────────────
# A compact small-caps companion to the 5x7 "big" font, so secondary text
# (status, countdown, table rows) reads as one designed pixel family instead of
# PIL's default bitmap. Uppercase-only; lookups upper-case the input. 3 wide,
# 5 tall, '#' = on. Use draw_micro / micro_text_width.

_GLYPHS_3x5 = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "##."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["#.#", "##.", "###", ".##", "#.#"],
    "O": ["###", "#.#", "#.#", "#.#", "###"],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": ["###", "#.#", "#.#", "###", "..#"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", ".#.", "#..", "###"],
    " ": ["...", "...", "...", "...", "..."],
    "-": ["...", "...", "###", "...", "..."],
    ":": ["...", ".#.", "...", ".#.", "..."],
    ".": ["...", "...", "...", "...", ".#."],
    "'": [".#.", ".#.", "...", "...", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "%": ["#.#", "..#", ".#.", "#..", "#.#"],
    "!": [".#.", ".#.", ".#.", "...", ".#."],
    "?": ["##.", "..#", ".#.", "...", ".#."],
}

MICRO_W = 3
MICRO_H = 5


def micro_text_width(text: str, spacing: int = 1) -> int:
    if not text:
        return 0
    return len(text) * (MICRO_W + spacing) - spacing


def draw_micro(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int] = WHITE,
    spacing: int = 1,
) -> None:
    """Render `text` in the 3x5 micro font (1:1, uppercase-only)."""
    x0, y0 = xy
    for ch in text:
        glyph = _GLYPHS_3x5.get(ch.upper()) or _GLYPHS_3x5[" "]
        for ry, row in enumerate(glyph):
            for cx, pixel in enumerate(row):
                if pixel == "#":
                    draw.point((x0 + cx, y0 + ry), fill=fill)
        x0 += MICRO_W + spacing


def draw_micro_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    fill: tuple[int, int, int] = WHITE,
    spacing: int = 1,
    x0: int = 0,
    x1: int = WIDTH,
) -> None:
    w = micro_text_width(text, spacing)
    x = x0 + ((x1 - x0) - w) // 2
    draw_micro(draw, (x, y), text, fill=fill, spacing=spacing)
