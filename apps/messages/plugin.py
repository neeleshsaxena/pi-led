from __future__ import annotations

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    BLUE,
    GLYPH_H,
    GREEN,
    HEIGHT,
    ORANGE,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    big_text_width,
    draw_big,
    new_canvas,
)
from pi_led_core.plugin import LedApp, RenderContext

# Named colors the admin can pick from for a message.
COLORS: dict[str, tuple[int, int, int]] = {
    "white": WHITE,
    "red": RED,
    "green": GREEN,
    "yellow": YELLOW,
    "orange": ORANGE,
    "blue": BLUE,
}

# Largest-to-smallest glyph scales we try when auto-fitting a message.
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
        # Word alone is too wide: break it.
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


def render_message(text: str, color: tuple[int, int, int]) -> Image.Image:
    """Center a static message on the 64x64, auto-sized to the largest scale
    that fits both width and height."""
    img = new_canvas()
    if not text:
        return img
    draw = ImageDraw.Draw(img)

    for scale in _SCALES:
        lines = _wrap(text, scale)
        line_h = GLYPH_H * scale
        gap = max(1, scale)
        total_h = len(lines) * line_h + (len(lines) - 1) * gap
        fits_w = all(big_text_width(ln, scale) <= WIDTH for ln in lines)
        if total_h <= HEIGHT and fits_w:
            y = (HEIGHT - total_h) // 2
            for ln in lines:
                x = (WIDTH - big_text_width(ln, scale)) // 2
                draw_big(draw, (x, y), ln, fill=color, scale=scale)
                y += line_h + gap
            return img

    # Fallback: smallest scale, clip vertically to what fits.
    scale = 1
    lines = _wrap(text, scale)
    line_h = GLYPH_H * scale + 1
    max_lines = HEIGHT // line_h
    y = 0
    for ln in lines[:max_lines]:
        x = (WIDTH - big_text_width(ln, scale)) // 2
        draw_big(draw, (x, y), ln, fill=color, scale=scale)
        y += line_h
    return img


class MessagesApp(LedApp):
    """Display a single static message typed in the admin. Text is uppercased
    (the 5x7 font is uppercase) and auto-fit to the panel."""

    id = "messages"
    name = "Message"

    def default_config(self) -> dict:
        return {"text": "PI LED READY", "color": "white"}

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        text = str(cfg.get("text", "")).upper()
        color = COLORS.get(str(cfg.get("color", "white")).lower(), WHITE)
        return render_message(text, color)
