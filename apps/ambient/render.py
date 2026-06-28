"""Ambient eye-candy effects — UI/UX-owned visuals.

Each effect is a small stateful class with `render(tick) -> 64x64 Image`. Heavy
per-pixel effects compute at a reduced internal resolution and scale up, which
keeps them smooth on a Pi 3B (the chunky look also suits an LED panel). The
plugin instantiates one per active view and keeps its state across frames.

To add an effect: write a class with `render(self, tick)`, add it to EFFECTS.
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
    new_canvas,
    scale_color,
)


class Plasma:
    """Classic shifting color field. Computed at 32x32, scaled 2x (bilinear)."""
    W = H = 32

    def render(self, tick: float) -> Image.Image:
        small = Image.new("RGB", (self.W, self.H))
        px = small.load()
        t = tick
        for y in range(self.H):
            for x in range(self.W):
                v = (
                    math.sin(x / 4.0 + t)
                    + math.sin(y / 3.0 - t)
                    + math.sin((x + y) / 5.0 + t)
                    + math.sin(math.hypot(x - 16, y - 16) / 4.0 - t)
                )
                px[x, y] = hsv_color((v + 4) / 8.0, 0.9, 1.0)
        return small.resize((WIDTH, HEIGHT), Image.BILINEAR)


class Fire:
    """Demoscene fire rising from the bottom. 32xH heat buffer, scaled up."""
    W = 32
    H = 32

    def __init__(self) -> None:
        self.heat = [[0.0] * self.W for _ in range(self.H)]

    @staticmethod
    def _color(v: float):
        v = max(0.0, min(1.0, v))
        if v < 0.33:
            return (int(v / 0.33 * 200), 0, 0)
        if v < 0.66:
            return (220, int((v - 0.33) / 0.33 * 180), 0)
        return (255, 230, int((v - 0.66) / 0.34 * 200))

    def render(self, tick: float) -> Image.Image:
        H, W, heat = self.H, self.W, self.heat
        for x in range(W):
            heat[H - 1][x] = random.random()
        for y in range(H - 1):
            for x in range(W):
                below = heat[y + 1][x]
                l = heat[y + 1][(x - 1) % W]
                r = heat[y + 1][(x + 1) % W]
                heat[y][x] = max(0.0, (below * 2 + l + r) / 4.0 - 0.010 - random.random() * 0.018)
        img = Image.new("RGB", (W, H))
        px = img.load()
        for y in range(H):
            for x in range(W):
                px[x, y] = self._color(heat[y][x])
        return img.resize((WIDTH, HEIGHT), Image.BILINEAR)


class MatrixRain:
    """Falling green code streams."""
    STEP = 4  # column spacing
    ROW = 6   # vertical spacing between glyphs

    def __init__(self) -> None:
        self.cols = WIDTH // self.STEP
        self.head = [random.uniform(-HEIGHT, 0) for _ in range(self.cols)]
        self.speed = [random.choice((2.0, 3.0, 4.0)) for _ in range(self.cols)]
        self.chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    def render(self, tick: float) -> Image.Image:
        img = new_canvas()
        draw = ImageDraw.Draw(img)
        for c in range(self.cols):
            x = c * self.STEP + 1
            self.head[c] += self.speed[c]
            if self.head[c] - 7 * self.ROW > HEIGHT:
                self.head[c] = random.uniform(-HEIGHT, 0)
                self.speed[c] = random.choice((2.0, 3.0, 4.0))
            head_y = int(self.head[c])
            for k in range(7):
                y = head_y - k * self.ROW
                if y < 0 or y >= HEIGHT:
                    continue
                ch = random.choice(self.chars)
                if k == 0:
                    col = (210, 255, 210)
                else:
                    g = max(0, 230 - k * 34)
                    col = (0, g, int(g * 0.25))
                draw_micro(draw, (x, y), ch, fill=col)
        return img


class Starfield:
    """Warp through a field of stars."""
    N = 80

    def __init__(self) -> None:
        self.stars = [[random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0.05, 1.0)] for _ in range(self.N)]

    def render(self, tick: float) -> Image.Image:
        img = new_canvas()
        draw = ImageDraw.Draw(img)
        cx, cy = WIDTH / 2, HEIGHT / 2
        for s in self.stars:
            s[2] -= 0.02
            if s[2] <= 0.02:
                s[0], s[1], s[2] = random.uniform(-1, 1), random.uniform(-1, 1), 1.0
            x = cx + (s[0] / s[2]) * cx
            y = cy + (s[1] / s[2]) * cy
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                b = int((1 - s[2]) * 255)
                draw.point((int(x), int(y)), fill=(b, b, b))
                if s[2] < 0.4:  # bright near stars get a little bloom
                    draw.point((int(x) + 1, int(y)), fill=(b // 2, b // 2, b // 2))
        return img


class Life:
    """Conway's Game of Life on a 32x32 grid (scaled 2x), auto-reseeding."""
    N = 32

    def __init__(self) -> None:
        self._seed()

    def _seed(self) -> None:
        self.board = [[random.random() < 0.3 for _ in range(self.N)] for _ in range(self.N)]
        self.age = 0
        self.stale = 0

    def render(self, tick: float) -> Image.Image:
        N, b = self.N, self.board
        nxt = [[False] * N for _ in range(N)]
        for y in range(N):
            for x in range(N):
                live = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx or dy:
                            if b[(y + dy) % N][(x + dx) % N]:
                                live += 1
                nxt[y][x] = live == 3 or (b[y][x] and live == 2)
        self.stale = self.stale + 1 if nxt == b else 0
        self.board = nxt
        self.age += 1
        if self.age > 600 or self.stale > 6:
            self._seed()
        small = Image.new("RGB", (N, N))
        px = small.load()
        col = hsv_color(tick * 0.02, 0.55, 1.0)
        for y in range(N):
            for x in range(N):
                if self.board[y][x]:
                    px[x, y] = col
        return small.resize((WIDTH, HEIGHT), Image.NEAREST)


# view id -> effect class. Order here defines the admin view order.
EFFECTS = {
    "plasma": Plasma,
    "matrix": MatrixRain,
    "fire": Fire,
    "starfield": Starfield,
    "life": Life,
}
