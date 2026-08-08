"""Transit departures — pixel rendering (functional scaffold; UI polish TBD).

A small departures board: a "DEPARTURES" header, then one block per configured
stop. Each block has a bright label line (stop in agency color + a big minute
countdown, green when imminent / red when late) and a detail line beneath — the
Caltrain train number + service, or the bus route + destination. No key / no
service get quiet hints.

Entry point: render_transit(board, has_key, tick). `board` is a list of
    {"label": str, "agency": str, "departures": [
        {"line","train","dest","direction","minutes","delayed"}, ...]}
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
    new_canvas,
    px_text_width,
    scale_color,
)

_AGENCY_COLOR = {"CT": RED, "SM": BLUE, "SF": GRAY, "BA": BLUE}
# Caltrain service names -> short tag.
_SERVICE = (("bullet", "BULLET"), ("limited", "LTD"), ("express", "EXP"), ("local", "LOCAL"))


def _agency_color(agency: str):
    return _AGENCY_COLOR.get((agency or "").upper(), ACCENT)


def _min_text(m: int) -> str:
    return "NOW" if m <= 0 else f"{m}m"


def _min_color(m: int, delayed: bool):
    if delayed:
        return RED
    if m <= 0:
        return LIME
    if m <= 3:
        return GREEN
    return WHITE


def _fit_px(text: str, max_w: int) -> str:
    while text and px_text_width(text, PX_SMALL) > max_w:
        text = text[:-1]
    return text


def _service_tag(line: str) -> str:
    low = (line or "").lower()
    for key, tag in _SERVICE:
        if key in low:
            return tag
    return ""


def _detail(agency: str, dep: dict) -> str:
    """Second line: Caltrain -> '#631 LOCAL'; bus -> '292 SAN MATEO'."""
    line = str(dep.get("line", "")).strip().upper()
    train = str(dep.get("train", "")).strip()
    dest = str(dep.get("dest", "")).strip().upper()
    if (agency or "").upper() == "CT":
        svc = _service_tag(dep.get("line", ""))
        return (f"#{train} {svc}".strip() if train else svc)[:13]
    # bus: route number + destination (the stop label already gives the place)
    return (f"{line} {dest}" if line else dest)[:13]


def render_transit(board, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_micro_centered(draw, 1, "DEPARTURES", fill=ACCENT)
    filled_rect(draw, 4, 7, WIDTH - 5, 7, scale_color(ACCENT, 0.5))

    if not has_key:
        draw_px_centered(draw, 22, "NEED", fill=WHITE, size=PX_SMALL)
        draw_px_centered(draw, 34, "511 KEY", fill=WHITE, size=PX_SMALL)
        return img

    if not board:
        draw_px_centered(draw, 28, "NO SVC", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        return img

    blocks = board[:3]
    for i, stop in enumerate(blocks):
        y = 10 + i * 18
        color = _agency_color(stop.get("agency", ""))
        label = str(stop.get("label", "")).upper()
        deps = stop.get("departures") or []

        # right side: big minute countdown (or "--"); then fit the label before it
        first = deps[0] if deps else None
        mt = _min_text(int(first["minutes"])) if first else "--"
        mc = _min_color(int(first["minutes"]), bool(first.get("delayed"))) if first else scale_color(WHITE, 0.5)
        mx = WIDTH - px_text_width(mt, PX_SMALL) - 1
        draw_px(draw, (mx, y), mt, fill=mc, size=PX_SMALL)
        draw_px(draw, (1, y), _fit_px(label, mx - 3), fill=color, size=PX_SMALL)
        if not first:
            continue

        # detail line: train#/route + destination, bright
        detail = _detail(stop.get("agency", ""), first)
        if detail:
            draw_micro(draw, (1, y + 9), detail, fill=WHITE)
    return img
