"""Local news — pixel rendering (UI-owned).

Pages headlines one at a time (instead of a hard-to-read horizontal ticker): the
place under a "LOCAL NEWS" header, then the headline word-wrapped in the readable
PX_SMALL font. Short headlines sit centered; long ones gently auto-scroll up
within the card so the whole thing reads. Paging dots below; "NO NEWS" when empty.

Entry point: render_news(headlines, place, tick) — headlines is a list of strings.
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
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_cap_height,
    px_text_width,
    scale_color,
)

DWELL = 6.0            # seconds each headline holds (longer for the scroll)
_CAP = px_cap_height(PX_SMALL)
_LINE_H = _CAP + 2
_CARD_TOP, _CARD_BOT = 19, 58


def _wrap(text: str, maxw: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if px_text_width(trial, PX_SMALL) <= maxw:
            cur = trial
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while px_text_width(word, PX_SMALL) > maxw and len(word) > 1:
            cut = len(word)
            while cut > 1 and px_text_width(word[:cut], PX_SMALL) > maxw:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


def _dots(draw, idx: int, n: int, color) -> None:
    if n <= 1:
        return
    if n * 5 - 2 <= WIDTH - 8:
        total = n * 5 - 2
        x0 = (WIDTH - total) // 2
        for i in range(n):
            x = x0 + i * 5
            if i == idx:
                filled_rect(draw, x, 61, x + 2, 63, color)
            else:
                draw.point((x + 1, 62), fill=scale_color(GRAY, 0.8))
    else:
        draw_micro_centered(draw, 61, f"{idx + 1}/{n}", fill=scale_color(GRAY, 0.85))


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

    if place_lbl:
        draw_micro_centered(draw, 12, place_lbl, fill=scale_color(CYAN, 0.8))

    n = len(headlines)
    idx = int(tick / DWELL) % n
    lines = _wrap(headlines[idx].upper(), WIDTH - 6)

    card_h = _CARD_BOT - _CARD_TOP
    block_h = len(lines) * _LINE_H - 2
    strip = Image.new("RGB", (WIDTH, max(block_h, card_h)), (0, 0, 0))
    sd = ImageDraw.Draw(strip)
    y = 0
    for ln in lines:
        draw_px_centered(sd, y, ln, fill=WHITE, size=PX_SMALL)
        y += _LINE_H

    if block_h <= card_h:                          # fits — center it
        img.paste(strip.crop((0, 0, WIDTH, block_h)), (0, _CARD_TOP + (card_h - block_h) // 2))
    else:                                          # too tall — pan up (hold, scroll, hold)
        t = (tick % DWELL) / DWELL
        p = 0.0 if t < 0.18 else (1.0 if t > 0.82 else (t - 0.18) / 0.64)
        off = int(p * (block_h - card_h))
        img.paste(strip.crop((0, off, WIDTH, off + card_h)), (0, _CARD_TOP))

    _dots(draw, idx, n, ACCENT)
    return img
