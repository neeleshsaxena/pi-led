"""Transit departures — pixel rendering (functional scaffold; UI polish TBD).

A small departures board: a "DEPARTURES" header, then one block per configured
stop showing its label, the next train/bus destination, and a big "minutes until"
countdown (green when imminent, red when the trip is running late). A second
upcoming departure is shown small beneath. No key / no service get quiet hints.

Entry point: render_transit(board, has_key, tick). `board` is a list of
    {"label": str, "agency": str, "departures": [
        {"line": str, "dest": str, "direction": str, "minutes": int, "delayed": bool}, ...]}
See deploy/UI-ASKS.md — the board layout is UI-owned polish.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    BLUE,
    GRAY,
    GREEN,
    LIME,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    draw_micro,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    micro_text_width,
    new_canvas,
    px_text_width,
    scale_color,
)

_AGENCY_COLOR = {"CT": RED, "SM": BLUE, "SF": GRAY, "BA": BLUE}


def _agency_color(agency: str):
    return _AGENCY_COLOR.get((agency or "").upper(), ACCENT)


def _min_text(m: int) -> str:
    if m <= 0:
        return "NOW"
    return f"{m}m"


def _min_color(m: int, delayed: bool):
    if delayed:
        return RED
    if m <= 3:
        return LIME if m <= 0 else GREEN
    return WHITE


def render_transit(board, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_micro_centered(draw, 1, "DEPARTURES", fill=ACCENT)
    filled_rect(draw, 4, 7, WIDTH - 5, 7, scale_color(ACCENT, 0.5))

    if not has_key:
        draw_px_centered(draw, 22, "NEED", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        draw_px_centered(draw, 34, "511 KEY", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        return img

    if not board:
        draw_px_centered(draw, 28, "NO SVC", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    blocks = board[:3]
    band = (64 - 10) // len(blocks)  # split the space below the header across stops
    for i, stop in enumerate(blocks):
        y = 10 + i * band
        color = _agency_color(stop.get("agency", ""))
        label = str(stop.get("label", "")).upper()[:9]
        draw_micro(draw, (2, y + 1), label, fill=color)

        deps = stop.get("departures") or []
        if not deps:
            txt = "--"
            draw_px(draw, (WIDTH - px_text_width(txt, PX_SMALL) - 1, y), txt, fill=GRAY, size=PX_SMALL)
            continue

        first = deps[0]
        mt = _min_text(int(first["minutes"]))
        mc = _min_color(int(first["minutes"]), bool(first.get("delayed")))
        draw_px(draw, (WIDTH - px_text_width(mt, PX_SMALL) - 1, y), mt, fill=mc, size=PX_SMALL)

        # destination under the label; second departure small on the right
        dest = str(first.get("dest", "")).upper()
        if dest:
            dest = dest[:10]
            draw_micro(draw, (2, y + 8), dest, fill=scale_color(WHITE, 0.7))
        if len(deps) > 1:
            nxt = f"+{int(deps[1]['minutes'])}"
            draw_micro(
                draw,
                (WIDTH - micro_text_width(nxt) - 1, y + 8),
                nxt,
                fill=scale_color(GRAY, 0.9),
            )
    return img
