"""Local news — pixel rendering (functional scaffold; UI polish TBD).

A classic news ticker: the headlines scroll right→left in one looping line, tinted
in alternating shades so each headline reads as a separate item, under a "LOCAL
NEWS" header, with the place named beneath. Empty feed shows a quiet "NO NEWS".

Entry point: render_news(headlines, place, tick) — headlines is a list of strings.
See deploy/UI-ASKS.md — the ticker vs. paged-card treatment is UI-owned polish.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GRAY,
    PX_SMALL,
    WHITE,
    WIDTH,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_cap_height,
    px_text_width,
    scale_color,
)

_SEP = "   •   "


def render_news(headlines, place, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, "LOCAL NEWS", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(ACCENT, 0.5))

    place_lbl = (place or "").upper()[:20]
    if not headlines:
        draw_px_centered(draw, 26, "NO NEWS", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        if place_lbl:
            draw_micro_centered(draw, 40, place_lbl, fill=scale_color(GRAY, 0.8))
        return img

    # alternating tints so consecutive headlines read as distinct
    tints = [scale_color(WHITE, 0.95), CYAN]
    parts = [(h.upper() + _SEP, tints[i % 2]) for i, h in enumerate(headlines)]
    widths = [px_text_width(t, PX_SMALL) for t, _ in parts]
    total = max(1, sum(widths))
    h = px_cap_height(PX_SMALL) + 2
    strip = Image.new("RGB", (total, h), (0, 0, 0))
    sd = ImageDraw.Draw(strip)
    x = 0
    for (t, c), w in zip(parts, widths):
        draw_px(sd, (x, 0), t, fill=c, size=PX_SMALL)
        x += w

    off = int((tick * 18) % total)
    view = Image.new("RGB", (WIDTH, h), (0, 0, 0))
    view.paste(strip, (-off, 0))
    view.paste(strip, (total - off, 0))  # second copy for a seamless loop
    img.paste(view, (0, 27))

    if place_lbl:
        draw_micro_centered(draw, 46, place_lbl, fill=scale_color(GRAY, 0.85))
    return img
