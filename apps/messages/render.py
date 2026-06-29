"""Visual layout + effects for the messages plugin — owned by the UI/UX workstream.

Pure rendering: given text + an RGB color (+ optional viz/tick), produce a 64x64
frame. No data, config, or controller concerns live here (those stay in
plugin.py).

Entry point: `render_message(text, color, viz="solid", tick=0.0)`. The `viz` and
`tick` params are OPTIONAL with defaults, so the existing `render_message(text,
color)` call keeps working until the backend is wired to pass them (see
deploy/UI-UX-WORKSTREAM.md). See deploy/UI-UX-WORKSTREAM.md for ownership.

Text is rendered in the kenpixel display font (crisp, no-AA). It's an uppercase
pixel font (lowercase input renders as caps) with full punctuation.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    HEIGHT,
    WIDTH,
    draw_px,
    hsv_color,
    new_canvas,
    px_cap_height,
    px_text_width,
    pulse_color,
    scale_color,
    sparkle,
)

# Effects the admin dropdown can offer. Keep in sync with the `viz` choices in
# admin.html and the UI-ASK. All are bright-on-black + flicker-safe (no dim
# full-field fills; pulses never drop near black).
VIZ_CHOICES = ("solid", "rainbow", "spectrum", "breathe", "wave", "scroll", "sparkle")

# Kenpixel is an 8px-grid font: crisp only at multiples of 8. Try biggest first.
_SIZES = (24, 16, 8)


def _line_gap(size: int) -> int:
    return max(3, size // 4)


def _wrap(text: str, size: int) -> list[str]:
    """Greedy word-wrap so each line fits WIDTH at `size`. Long single words are
    hard-broken character by character."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if px_text_width(trial, size) <= WIDTH:
            current = trial
            continue
        if current:
            lines.append(current)
            current = ""
        if px_text_width(word, size) <= WIDTH:
            current = word
            continue
        part = ""
        for ch in word:
            if px_text_width(part + ch, size) <= WIDTH:
                part += ch
            else:
                lines.append(part)
                part = ch
        current = part
    if current:
        lines.append(current)
    return lines


def _fit(text: str):
    """Pick the largest size whose wrapped lines fit the panel. Returns
    (size, lines, total_h) or falls back to the smallest size, clipped."""
    words = text.split()
    for size in _SIZES:
        # skip sizes where a single word is wider than the panel — that forces
        # ugly mid-word breaks; a smaller size wraps on word boundaries instead.
        if words and max(px_text_width(w, size) for w in words) > WIDTH:
            continue
        lines = _wrap(text, size)
        line_h = px_cap_height(size) + _line_gap(size)
        total_h = len(lines) * line_h - _line_gap(size)
        if total_h <= HEIGHT:
            return size, lines, total_h
    size = 8
    lines = _wrap(text, size)
    line_h = px_cap_height(size) + _line_gap(size)
    max_lines = max(1, (HEIGHT + _line_gap(size)) // line_h)
    lines = lines[:max_lines]
    return size, lines, len(lines) * line_h - _line_gap(size)


def _line_positions(lines, size, total_h):
    """Yield (x, y, line) centered as a block."""
    line_h = px_cap_height(size) + _line_gap(size)
    y = (HEIGHT - total_h) // 2
    for ln in lines:
        x = (WIDTH - px_text_width(ln, size)) // 2
        yield x, y, ln
        y += line_h


def _draw_chars(draw, x, y, text, size, *, color_fn=None, dy_fn=None, fill=None):
    """Draw `text` char-by-char advancing by each glyph's real width (kenpixel is
    variable-width), so per-character effects (hue, bob) stay aligned."""
    cx = x
    for i, ch in enumerate(text):
        col = color_fn(i, cx) if color_fn else fill
        oy = dy_fn(i) if dy_fn else 0
        draw_px(draw, (cx, y + oy), ch, fill=col, size=size)
        cx += px_text_width(ch, size)


# ── effects ──────────────────────────────────────────────────────────────────


def _solid(draw, text, color, tick):
    size, lines, total_h = _fit(text)
    for x, y, ln in _line_positions(lines, size, total_h):
        draw_px(draw, (x, y), ln, fill=color, size=size)


def _rainbow(draw, text, color, tick):
    """Whole message cycles smoothly through the spectrum."""
    size, lines, total_h = _fit(text)
    col = hsv_color(tick * 0.18)
    for x, y, ln in _line_positions(lines, size, total_h):
        draw_px(draw, (x, y), ln, fill=col, size=size)


def _spectrum(draw, text, color, tick):
    """Each character a different hue; the rainbow drifts across the text."""
    size, lines, total_h = _fit(text)
    for x, y, ln in _line_positions(lines, size, total_h):
        _draw_chars(draw, x, y, ln, size,
                    color_fn=lambda i, cx: hsv_color(tick * 0.12 + cx * 0.014))


def _breathe(draw, text, color, tick):
    """Gently brightens/dims in the chosen color (never near black)."""
    size, lines, total_h = _fit(text)
    col = pulse_color(color, tick, period=2.2, min_factor=0.55)
    for x, y, ln in _line_positions(lines, size, total_h):
        draw_px(draw, (x, y), ln, fill=col, size=size)


def _wave(draw, text, color, tick):
    """Each character bobs on a travelling sine wave."""
    size, lines, total_h = _fit(text)
    amp = max(2, size // 6)
    for x, y, ln in _line_positions(lines, size, total_h):
        _draw_chars(draw, x, y, ln, size, fill=color,
                    dy_fn=lambda i: int(round(math.sin(tick * 3.0 + i * 0.7) * amp)))


def _scroll(draw, text, color, tick):
    """Marquee: the message scrolls right→left on one big line. Great for long
    text that won't fit statically."""
    size = 24 if px_cap_height(24) <= HEIGHT - 8 else 16
    w = px_text_width(text, size)
    y = (HEIGHT - px_cap_height(size)) // 2
    travel = w + WIDTH
    x = WIDTH - int((tick * 22) % travel)
    draw_px(draw, (x, y), text, fill=color, size=size)


def _sparkle(draw, text, color, tick):
    """Solid message with twinkling confetti around it."""
    sparkle(draw, tick, count=16, seed=11)
    _solid(draw, text, color, tick)


_EFFECTS = {
    "solid": _solid,
    "rainbow": _rainbow,
    "spectrum": _spectrum,
    "breathe": _breathe,
    "wave": _wave,
    "scroll": _scroll,
    "sparkle": _sparkle,
}


def render_message(
    text: str,
    color: tuple[int, int, int],
    viz: str = "solid",
    tick: float = 0.0,
) -> Image.Image:
    """Render a message to a 64x64 frame using the named `viz` effect.

    Backward-compatible: `render_message(text, color)` still renders a static
    centered message (viz="solid", tick=0)."""
    img = new_canvas()
    if not text:
        return img
    draw = ImageDraw.Draw(img)
    effect = _EFFECTS.get((viz or "solid").lower(), _solid)
    effect(draw, text, color, tick)
    return img
