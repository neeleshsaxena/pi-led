"""Transit departures — pixel rendering (UI-owned).

Pages one stop at a time (instead of three crammed blocks) for legibility: the
stop in its agency colour, the next departure's route + destination, a BIG minute
countdown (green imminent / red late), and the one after it, with paging dots.
No key → "NEED 511 KEY"; empty board → "NO SVC".

Entry point: render_transit(board, has_key, tick). `board` is a list of
    {"label": str, "agency": str, "departures": [
        {"line","train","dest","direction","minutes","delayed"}, ...]}
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    BLUE,
    GRAY,
    GREEN,
    LIME,
    PX_BIG,
    PX_SMALL,
    RED,
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

DWELL = 4.0  # seconds each stop holds before paging to the next
_AGENCY_COLOR = {"CT": RED, "SM": BLUE, "SF": GRAY, "BA": BLUE}
_SERVICE = (("bullet", "BULLET"), ("limited", "LTD"), ("express", "EXP"), ("local", "LOCAL"))


def _agency_color(agency: str):
    return _AGENCY_COLOR.get((agency or "").upper(), ACCENT)


def _min_color(m: int, delayed: bool):
    if delayed:
        return RED
    if m <= 0:
        return LIME
    if m <= 3:
        return GREEN
    return WHITE


def _service_tag(line: str) -> str:
    low = (line or "").lower()
    for key, tag in _SERVICE:
        if key in low:
            return tag
    return ""


def _detail(agency: str, dep: dict) -> str:
    """Route + destination line: Caltrain -> '#631 LOCAL'; bus -> '292 SAN MATEO'."""
    line = str(dep.get("line", "")).strip().upper()
    train = str(dep.get("train", "")).strip()
    dest = str(dep.get("dest", "")).strip().upper()
    if (agency or "").upper() == "CT":
        # train # + destination so the direction is clear (e.g. "#631 SF")
        return f"#{train} {dest}".strip() if train else (dest or _service_tag(dep.get("line", "")))
    return f"{line} {dest}".strip() if line else dest


def _fit(text: str, max_w: int) -> str:
    while text and px_text_width(text, PX_SMALL) > max_w:
        text = text[:-1]
    return text


def _dots(draw, idx: int, n: int, color) -> None:
    if n <= 1:
        return
    total = n * 5 - 2
    x0 = (WIDTH - total) // 2
    for i in range(n):
        x = x0 + i * 5
        if i == idx:
            filled_rect(draw, x, 61, x + 2, 62, color)
        else:
            draw.point((x + 1, 61 + 1), fill=scale_color(GRAY, 0.8))


def render_transit(board, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 1, "DEPARTURES", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 4, 9, WIDTH - 5, 9, scale_color(ACCENT, 0.5))

    if not has_key:
        draw_px_centered(draw, 24, "NEED", fill=WHITE, size=PX_SMALL)
        draw_px_centered(draw, 36, "511 KEY", fill=WHITE, size=PX_SMALL)
        return img
    if not board:
        draw_px_centered(draw, 28, "NO SVC", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        return img

    n = len(board)
    idx = int(tick / DWELL) % n
    stop = board[idx]
    color = _agency_color(stop.get("agency", ""))
    deps = stop.get("departures") or []

    # stop name in agency colour
    draw_px_centered(draw, 12, _fit(str(stop.get("label", "")).upper(), WIDTH - 4), fill=color, size=PX_SMALL)

    if not deps:
        draw_px_centered(draw, 32, "NO SVC", fill=scale_color(WHITE, 0.6), size=PX_SMALL)
        _dots(draw, idx, n, color)
        return img

    first = deps[0]
    # route + destination (readable PX_SMALL, was micro)
    draw_px_centered(draw, 22, _fit(_detail(stop.get("agency", ""), first), WIDTH - 2), fill=WHITE, size=PX_SMALL)

    # BIG minute countdown — the hero number
    m = int(first.get("minutes", 0))
    mc = _min_color(m, bool(first.get("delayed")))
    if m <= 0:
        draw_px_centered(draw, 33, "NOW", fill=mc, size=PX_BIG)
    else:
        num = str(m)
        nw = px_text_width(num, PX_BIG)
        gap = 2
        unit_w = px_text_width("MIN", PX_SMALL)
        x0 = (WIDTH - (nw + gap + unit_w)) // 2
        draw_px(draw, (x0, 33), num, fill=mc, size=PX_BIG)
        draw_px(draw, (x0 + nw + gap, 33 + px_cap_height(PX_BIG) - px_cap_height(PX_SMALL)),
                "MIN", fill=scale_color(mc, 0.9), size=PX_SMALL)

    # the one after, small + dim
    if len(deps) > 1:
        m2 = int(deps[1].get("minutes", 0))
        then = "THEN NOW" if m2 <= 0 else f"THEN {m2} MIN"
        draw_micro_centered(draw, 52, then, fill=scale_color(WHITE, 0.6))

    _dots(draw, idx, n, color)
    return img
