"""Ambient eye-candy effects — UI/UX-owned visuals.

Each effect is a small stateful class with `render(tick) -> 64x64 Image`. Heavy
per-pixel effects compute at a reduced internal resolution and scale up, which
keeps them smooth on a Pi 3B (the chunky look also suits an LED panel). The
plugin instantiates one per active view and keeps its state across frames.

Tuned for the HUB75 panel: it runs dim with a blown-out, saturated response, so
everything here pushes saturation/value high and favours bright-on-true-black
over dim full-field washes (which strobe). To add an effect: write a class with
`render(self, tick)`, add it to EFFECTS.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    HEIGHT,
    WIDTH,
    draw_micro,
    hsv_color,
    lerp_color,
    new_canvas,
    scale_color,
)


def _gradient(stops: list[tuple[float, tuple[int, int, int]]], n: int = 256) -> list[tuple[int, int, int]]:
    """Build an `n`-entry RGB lookup from (position, color) stops (positions
    0..1, ascending). Lets per-pixel effects map a 0..1 intensity to a rich
    multi-stop ramp with a single list index (no per-pixel math)."""
    lut: list[tuple[int, int, int]] = []
    for i in range(n):
        t = i / (n - 1)
        # find the segment t falls in
        for j in range(len(stops) - 1):
            p0, c0 = stops[j]
            p1, c1 = stops[j + 1]
            if t <= p1 or j == len(stops) - 2:
                span = max(1e-6, p1 - p0)
                lut.append(lerp_color(c0, c1, (t - p0) / span))
                break
    return lut


class Plasma:
    """Classic shifting color field with a slowly rotating full-spectrum
    palette so it never sits in one hue. Computed at 40x40, scaled up bilinear."""
    W = H = 40

    def render(self, tick: float) -> Image.Image:
        small = Image.new("RGB", (self.W, self.H))
        px = small.load()
        t = tick
        cx = cy = self.W / 2
        spin = tick * 0.05  # slow whole-frame hue rotation
        for y in range(self.H):
            for x in range(self.W):
                v = (
                    math.sin(x / 5.0 + t)
                    + math.sin(y / 4.0 - t * 0.9)
                    + math.sin((x + y) / 6.0 + t * 0.7)
                    + math.sin(math.hypot(x - cx, y - cy) / 4.5 - t)
                )
                # tighter contrast bands + spin keeps the whole spectrum moving
                hue = v / 8.0 + spin
                px[x, y] = hsv_color(hue, 0.95, 1.0)
        return small.resize((WIDTH, HEIGHT), Image.BILINEAR)


class Aurora:
    """Flowing aurora curtains — green at the base shading to violet, bright
    ribbons drifting on true black. Low-res field scaled up bilinear."""
    W = 40
    H = 40

    def render(self, tick: float) -> Image.Image:
        small = Image.new("RGB", (self.W, self.H))
        px = small.load()
        t = tick
        H, W = self.H, self.W
        for y in range(H):
            fy = y / H
            # curtains rise: brighter low, fading to black at the top
            vfade = max(0.0, 1.0 - fy) ** 0.7
            # hue climbs green(0.30) -> cyan/blue -> violet(0.55) going up
            base_hue = 0.30 + 0.25 * fy
            for x in range(W):
                band = math.sin(x / 5.0 + t) + math.sin((x * 0.7 - y * 0.4) / 4.0 - t * 0.6)
                # sharpen the ribbon so the gaps fall to black (bright-on-black)
                ribbon = (0.5 + 0.5 * math.sin(band * 1.2 + t)) ** 2.0
                v = ribbon * vfade
                hue = base_hue + 0.07 * math.sin(band + t * 0.3)
                px[x, y] = hsv_color(hue, 0.9, min(1.0, v * 1.25))
        return small.resize((WIDTH, HEIGHT), Image.BILINEAR)


class _HeatField:
    """Shared demoscene heat simulation rising from the bottom. Subclasses set
    a PALETTE (256-entry RGB ramp) and optional cooling/seed tuning."""
    W = 36
    H = 36
    PALETTE: list[tuple[int, int, int]] = []
    COOLING = 0.012      # base heat lost per row
    COOL_JITTER = 0.020  # extra random cooling (turbulence)
    SEED_LO = 0.55       # bottom-row heat range
    SEED_HI = 1.0

    def __init__(self) -> None:
        self.heat = [[0.0] * self.W for _ in range(self.H)]

    def render(self, tick: float) -> Image.Image:
        H, W, heat = self.H, self.W, self.heat
        for x in range(W):
            heat[H - 1][x] = self.SEED_LO + random.random() * (self.SEED_HI - self.SEED_LO)
        cool, jitter = self.COOLING, self.COOL_JITTER
        for y in range(H - 1):
            row, below = heat[y], heat[y + 1]
            for x in range(W):
                avg = (below[x] * 2 + below[(x - 1) % W] + below[(x + 1) % W]) / 4.0
                row[x] = max(0.0, avg - cool - random.random() * jitter)
        lut = self.PALETTE
        last = len(lut) - 1
        img = Image.new("RGB", (W, H))
        px = img.load()
        for y in range(H):
            r = heat[y]
            for x in range(W):
                px[x, y] = lut[int(r[x] * last) if r[x] < 1.0 else last]
        return img.resize((WIDTH, HEIGHT), Image.BILINEAR)


class Fire(_HeatField):
    """Demoscene fire — true-black floor, deep red core, blowing out to white."""
    PALETTE = _gradient([
        (0.00, (0, 0, 0)),
        (0.12, (28, 0, 0)),
        (0.32, (170, 14, 0)),
        (0.55, (244, 78, 0)),
        (0.78, (255, 180, 26)),
        (1.00, (255, 248, 200)),
    ])


class Embers:
    """Warm ember bed — low glowing coals, no white blow-out. Same heat sim as
    Fire but cooler/shorter flames and a red-amber-only ramp."""
    # composed (not subclassed-and-overridden) so the registry stays explicit
    PALETTE = _gradient([
        (0.00, (0, 0, 0)),
        (0.18, (40, 0, 0)),
        (0.42, (130, 10, 0)),
        (0.66, (214, 48, 0)),
        (0.86, (255, 116, 6)),
        (1.00, (255, 182, 60)),
    ])

    class _Field(_HeatField):
        COOLING = 0.030      # cooler -> shorter, settled coals
        COOL_JITTER = 0.026
        SEED_LO = 0.45
        SEED_HI = 0.95

    def __init__(self) -> None:
        self._f = self._Field()
        self._f.PALETTE = self.PALETTE

    def render(self, tick: float) -> Image.Image:
        return self._f.render(tick)


class MatrixRain:
    """Falling green code streams with a stable glyph grid (glyphs shimmer
    occasionally instead of strobing every frame) and bright white heads."""
    STEP = 4   # column spacing
    ROW = 6    # vertical spacing between glyphs

    def __init__(self) -> None:
        self.cols = WIDTH // self.STEP
        self.rows = HEIGHT // self.ROW + 2
        self.chars = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789:.=*+"
        self.head = [random.uniform(-HEIGHT, 0) for _ in range(self.cols)]
        self.speed = [random.choice((1.6, 2.2, 3.0, 3.6)) for _ in range(self.cols)]
        self.trail = [random.randint(7, 12) for _ in range(self.cols)]
        # persistent glyph per (col, glyph-row) so they don't re-randomise wildly
        self.glyphs = [[random.choice(self.chars) for _ in range(self.rows)] for _ in range(self.cols)]

    def render(self, tick: float) -> Image.Image:
        img = new_canvas()
        draw = ImageDraw.Draw(img)
        # shimmer: mutate a handful of glyphs per frame (life without strobe)
        for _ in range(6):
            c = random.randrange(self.cols)
            self.glyphs[c][random.randrange(self.rows)] = random.choice(self.chars)
        for c in range(self.cols):
            x = c * self.STEP + 1
            self.head[c] += self.speed[c]
            tlen = self.trail[c]
            if self.head[c] - tlen * self.ROW > HEIGHT:
                self.head[c] = random.uniform(-HEIGHT, 0)
                self.speed[c] = random.choice((1.6, 2.2, 3.0, 3.6))
                self.trail[c] = random.randint(7, 12)
                tlen = self.trail[c]
            head_y = int(self.head[c])
            for k in range(tlen):
                y = head_y - k * self.ROW
                if y < 0 or y >= HEIGHT:
                    continue
                gi = (y // self.ROW) % self.rows
                ch = self.glyphs[c][gi]
                if k == 0:
                    col = (215, 255, 220)        # bright white-green head
                elif k == 1:
                    col = (130, 255, 150)         # hot green just behind
                else:
                    f = 1.0 - (k - 1) / max(1, tlen - 1)
                    g = int(40 + 205 * f)
                    col = (0, g, int(g * 0.30))
                draw_micro(draw, (x, y), ch, fill=col)
        return img


class Starfield:
    """Warp through a field of stars — bright, streaking, faintly tinted. Near
    stars get a 2x2 core + bloom and a motion streak toward where they came."""
    N = 150
    SPEED = 0.03

    def __init__(self) -> None:
        self.stars = [self._spawn(random.uniform(0.1, 1.0)) for _ in range(self.N)]

    @staticmethod
    def _spawn(z: float = 1.0) -> list[float]:
        # x, y in [-1,1], depth z, hue, sat
        return [
            random.uniform(-1, 1), random.uniform(-1, 1), z,
            random.random(),
            0.0 if random.random() < 0.5 else random.uniform(0.4, 0.8),
        ]

    def render(self, tick: float) -> Image.Image:
        img = new_canvas()
        draw = ImageDraw.Draw(img)
        cx, cy = WIDTH / 2, HEIGHT / 2
        for s in self.stars:
            pz = s[2]
            s[2] -= self.SPEED
            if s[2] <= 0.02:
                s[:] = self._spawn()
                continue
            x = cx + (s[0] / s[2]) * cx
            y = cy + (s[1] / s[2]) * cy
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                continue
            # ramps up fast so most on-screen stars read bright
            b = min(1.0, (1.0 - s[2]) ** 0.8 + 0.18)
            col = scale_color(hsv_color(s[3], s[4], 1.0), b)
            ix, iy = int(x), int(y)
            if s[2] < 0.6:
                # streak tail from the deeper previous projection
                px = cx + (s[0] / pz) * cx
                py = cy + (s[1] / pz) * cy
                draw.line([(int(px), int(py)), (ix, iy)], fill=scale_color(col, 0.6))
            draw.point((ix, iy), fill=col)
            if s[2] < 0.4:  # near stars: fat bright core + bloom
                halo = scale_color(col, 0.5)
                draw.point((ix + 1, iy), fill=col)
                draw.point((ix, iy + 1), fill=col)
                draw.point((ix + 1, iy + 1), fill=halo)
                draw.point((ix - 1, iy), fill=halo)
                draw.point((ix, iy - 1), fill=halo)
        return img


class Life:
    """Conway's Game of Life (32x32, scaled 2x NEAREST). Cells flash white at
    birth, settle into a slowly cycling vivid hue with age, and leave a brief
    cool ghost when they die. Auto-reseeds when stale."""
    N = 32

    def __init__(self) -> None:
        self._seed()

    def _seed(self) -> None:
        self.board = [[random.random() < 0.3 for _ in range(self.N)] for _ in range(self.N)]
        self.age = [[0] * self.N for _ in range(self.N)]
        self.glow = [[0.0] * self.N for _ in range(self.N)]  # fading death trail
        self.gen = 0
        self.stale = 0

    def render(self, tick: float) -> Image.Image:
        N, b = self.N, self.board
        nxt = [[False] * N for _ in range(N)]
        for y in range(N):
            for x in range(N):
                live = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if (dx or dy) and b[(y + dy) % N][(x + dx) % N]:
                            live += 1
                nxt[y][x] = live == 3 or (b[y][x] and live == 2)
        self.stale = self.stale + 1 if nxt == b else 0

        age, glow = self.age, self.glow
        base_hue = tick * 0.03
        small = Image.new("RGB", (N, N))
        px = small.load()
        for y in range(N):
            for x in range(N):
                was, now = b[y][x], nxt[y][x]
                if now:
                    a = age[y][x] + 1 if was else 0
                    age[y][x] = a
                    glow[y][x] = 1.0
                    hue = base_hue + (x + y) * 0.012
                    if a == 0:
                        px[x, y] = (235, 255, 245)            # birth flash
                    elif a < 3:
                        px[x, y] = hsv_color(hue, 0.75, 1.0)  # young, hot
                    else:
                        px[x, y] = hsv_color(hue, 0.95, 0.9)  # mature, saturated
                else:
                    age[y][x] = 0
                    g = glow[y][x]
                    if g > 0.04:
                        glow[y][x] = g * 0.45
                        px[x, y] = scale_color((40, 70, 150), g)  # cool death ghost

        self.board = nxt
        self.gen += 1
        if self.gen > 600 or self.stale > 6:
            self._seed()
        return small.resize((WIDTH, HEIGHT), Image.NEAREST)


# view id -> effect class. Order here defines the admin view order.
EFFECTS = {
    "plasma": Plasma,
    "aurora": Aurora,
    "matrix": MatrixRain,
    "fire": Fire,
    "embers": Embers,
    "starfield": Starfield,
    "life": Life,
}
