"""Visual layout + effects for the messages plugin — owned by the UI/UX workstream.

Pure rendering: given text + an RGB color (+ optional viz/tick), produce a 64x64
frame. No data, config, or controller concerns live here (those stay in
plugin.py).

Entry point: `render_message(text, color, viz="solid", tick=0.0)`. The `viz` and
`tick` params are OPTIONAL with defaults, so the existing `render_message(text,
color)` call keeps working until the backend is wired to pass them (see
deploy/UI-ASKS.md). See deploy/UI-UX-WORKSTREAM.md for ownership boundaries.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    GLYPH_H,
    GLYPH_W,
    HEIGHT,
    WIDTH,
    big_text_width,
    draw_big,
    hsv_color,
    new_canvas,
    pulse_color,
    scale_color,
    sparkle,
)

# Effects the admin dropdown can offer. Keep in sync with the `viz` choices in
# admin.html and the UI-ASK. All are bright-on-black + flicker-safe (no dim
# full-field fills; pulses never drop near black).
VIZ_CHOICES = ("solid", "rainbow", "spectrum", "breathe", "wave", "scroll", "sparkle")

# Largest-to-smallest glyph scales we try when auto-fitting a static message.
_SCALES = (4, 3, 2, 1)


def _wrap(text: str, scale: int, spacing: int = 1) -> list[str]:
    """Greedy word-wrap so each line fits WIDTH at `scale`. Long single words
    are hard-broken character by character."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if big_text_width(trial, scale, spacing) <= WIDTH:
            current = trial
            continue
        if current:
            lines.append(current)
            current = ""
        if big_text_width(word, scale, spacing) <= WIDTH:
            current = word
            continue
        part = ""
        for ch in word:
            if big_text_width(part + ch, scale, spacing) <= WIDTH:
                part += ch
            else:
                lines.append(part)
                part = ch
        current = part
    if current:
        lines.append(current)
    return lines


def _fit(text: str):
    """Pick the largest scale whose wrapped lines fit the panel. Returns
    (scale, lines, total_h) or falls back to scale 1 clipped."""
    for scale in _SCALES:
        lines = _wrap(text, scale)
        line_h = GLYPH_H * scale
        gap = max(1, scale)
        total_h = len(lines) * line_h + (len(lines) - 1) * gap
        fits_w = all(big_text_width(ln, scale) <= WIDTH for ln in lines)
        if total_h <= HEIGHT and fits_w:
            return scale, lines, total_h
    scale = 1
    lines = _wrap(text, scale)
    line_h = GLYPH_H * scale + 1
    max_lines = HEIGHT // line_h
    return scale, lines[:max_lines], len(lines[:max_lines]) * line_h


def _line_positions(lines, scale, total_h):
    """Yield (x, y, line) centered as a block."""
    line_h = GLYPH_H * scale
    gap = max(1, scale)
    y = (HEIGHT - total_h) // 2
    for ln in lines:
        x = (WIDTH - big_text_width(ln, scale)) // 2
        yield x, y, ln
        y += line_h + gap


# ── effects ──────────────────────────────────────────────────────────────────


def _solid(draw, text, color, tick):
    scale, lines, total_h = _fit(text)
    for x, y, ln in _line_positions(lines, scale, total_h):
        draw_big(draw, (x, y), ln, fill=color, scale=scale)


def _rainbow(draw, text, color, tick):
    """Whole message cycles smoothly through the spectrum."""
    scale, lines, total_h = _fit(text)
    col = hsv_color(tick * 0.18)
    for x, y, ln in _line_positions(lines, scale, total_h):
        draw_big(draw, (x, y), ln, fill=col, scale=scale)


def _spectrum(draw, text, color, tick):
    """Each character a different hue; the rainbow drifts across the text."""
    scale, lines, total_h = _fit(text)
    step = GLYPH_W * scale + 1
    for x, y, ln in _line_positions(lines, scale, total_h):
        cx = x
        for i, ch in enumerate(ln):
            col = hsv_color(tick * 0.12 + (x + cx) * 0.012)
            draw_big(draw, (cx, y), ch, fill=col, scale=scale)
            cx += step


def _breathe(draw, text, color, tick):
    """Gently brightens/dims in the chosen color (never near black)."""
    scale, lines, total_h = _fit(text)
    col = pulse_color(color, tick, period=2.2, min_factor=0.55)
    for x, y, ln in _line_positions(lines, scale, total_h):
        draw_big(draw, (x, y), ln, fill=col, scale=scale)


def _wave(draw, text, color, tick):
    """Each character bobs on a travelling sine wave."""
    import math
    scale, lines, total_h = _fit(text)
    step = GLYPH_W * scale + 1
    amp = max(2, scale)
    for x, y, ln in _line_positions(lines, scale, total_h):
        cx = x
        for i, ch in enumerate(ln):
            dy = int(round(math.sin(tick * 3.0 + i * 0.7) * amp))
            draw_big(draw, (cx, y + dy), ch, fill=color, scale=scale)
            cx += step


def _scroll(draw, text, color, tick):
    """Marquee: the message scrolls right→left on one big line. Great for long
    text that won't fit statically."""
    # pick the biggest scale that fits the height on a single line
    scale = 4
    while scale > 1 and GLYPH_H * scale > HEIGHT - 8:
        scale -= 1
    w = big_text_width(text, scale)
    y = (HEIGHT - GLYPH_H * scale) // 2
    travel = w + WIDTH
    x = WIDTH - int((tick * 22) % travel)
    draw_big(draw, (x, y), text, fill=color, scale=scale)


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
