"""Traffic incidents — pixel rendering (functional scaffold; UI polish TBD).

Pages through nearby incidents one card at a time under a "TRAFFIC" header: a
type badge (ROADWORK / CRASH / HAZARD, colored), the road as the hero line, the
affected segment word-wrapped, and a distance + area footer, with paging dots.
No incidents in range → a green "ROADS CLEAR"; no key → "NEED 511 KEY".

Entry point: render_traffic(events, has_key, tick). `events` is a list of
    {"road","type","subtype","severity","where","dist_km","area"} (worst first).
See deploy/UI-ASKS.md — the card layout is UI-owned polish.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    GRAY,
    GREEN,
    ORANGE,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro,
    draw_micro_centered,
    draw_px_centered,
    filled_rect,
    micro_text_width,
    new_canvas,
    px_text_width,
    scale_color,
)

PAGE_SECS = 3.5  # how long each incident card is shown before paging to the next


def _badge(event: dict):
    """(short label, color) for the incident type."""
    etype = str(event.get("type", "")).upper()
    subtype = str(event.get("subtype", "")).lower()
    if etype == "CONSTRUCTION":
        return "ROADWORK", ORANGE
    if etype == "INCIDENT":
        return ("CRASH" if "collision" in subtype else "INCIDENT"), RED
    if etype == "SPECIAL_EVENT":
        return "EVENT", YELLOW
    if etype == "ROAD_CONDITION":
        return "HAZARD", YELLOW
    return (etype[:8] or "ALERT"), ACCENT


def _wrap_micro(text: str, max_chars: int = 15, max_lines: int = 2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w[:max_chars]
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines[:max_lines]


def render_traffic(events, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_micro_centered(draw, 1, "TRAFFIC", fill=ACCENT)
    filled_rect(draw, 4, 7, WIDTH - 5, 7, scale_color(ACCENT, 0.5))

    if not has_key:
        draw_px_centered(draw, 22, "NEED", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        draw_px_centered(draw, 34, "511 KEY", fill=scale_color(WHITE, 0.8), size=PX_SMALL)
        return img

    if not events:
        draw_px_centered(draw, 24, "ROADS", fill=GREEN, size=PX_SMALL)
        draw_px_centered(draw, 36, "CLEAR", fill=GREEN, size=PX_SMALL)
        return img

    n = len(events)
    page = int(tick / PAGE_SECS) % n
    e = events[page]
    label, color = _badge(e)

    # type badge
    draw_micro_centered(draw, 11, label, fill=color)

    # road as the hero line — PX_SMALL if it fits, else micro
    road = str(e.get("road", "")).upper() or "ROAD"
    if px_text_width(road, PX_SMALL) <= WIDTH - 2:
        draw_px_centered(draw, 19, road, fill=WHITE, size=PX_SMALL)
        wy = 31
    else:
        draw_micro_centered(draw, 21, road, fill=WHITE)
        wy = 29

    # affected segment, wrapped
    where = str(e.get("where", "")).upper()
    if where:
        for i, ln in enumerate(_wrap_micro(where)):
            draw_micro_centered(draw, wy + i * 7, ln, fill=scale_color(WHITE, 0.65))

    # footer: distance + area
    dist = e.get("dist_km")
    area = str(e.get("area", "")).upper()
    foot = f"{dist}KM" if dist is not None else ""
    if area:
        foot = f"{foot}  {area}"[:18].strip()
    if foot:
        draw_micro_centered(draw, 50, foot, fill=scale_color(GRAY, 0.9))

    # paging dots
    if n > 1:
        dots = min(n, 8)
        gap = 4
        total = dots * gap - (gap - 2)
        x0 = (WIDTH - total) // 2
        for i in range(dots):
            on = i == (page % dots)
            filled_rect(draw, x0 + i * gap, 60, x0 + i * gap + 1, 61,
                        color if on else scale_color(GRAY, 0.4))
    return img
