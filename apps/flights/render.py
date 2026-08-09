"""Flight board — pixel rendering (functional scaffold; UI polish TBD).

Pages one flight at a time (legible on 64px): a section header (SFO DEP orange /
SFO ARR cyan), the flight number, the other city, the scheduled local time +
minutes-until, and a colored status line, with paging dots. Cycles through the
next departures then the next arrivals. No key -> "NEED RAPIDAPI KEY".

Entry point: render_flights(departures, arrivals, has_key, tick). Each flight is
    {"number","airline","city","iata","time","minutes","status","delay_min",
     "terminal","gate","kind"}.
See deploy/UI-ASKS.md — a multi-row board layout is a UI-owned option.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    CYAN,
    GRAY,
    GREEN,
    ORANGE,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    draw_px_centered,
    filled_rect,
    new_canvas,
    scale_color,
)

DWELL = 4.0  # seconds each flight card holds before paging


def _fit(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars]


def _fmt12(hhmm: str) -> str:
    """'14:45' -> '2:45P'; '09:05' -> '9:05A'."""
    try:
        h, m = hhmm.split(":")
        h = int(h)
        ap = "A" if h < 12 else "P"
        h12 = h % 12 or 12
        return f"{h12}:{m}{ap}"
    except (ValueError, AttributeError):
        return hhmm or ""


def _status(flight: dict):
    """(label, color) for a flight's status."""
    st = str(flight.get("status", "")).upper()
    delay = int(flight.get("delay_min", 0))
    if st in ("CANCELED", "CANCELLED"):
        return "CANCELED", RED
    if st == "DIVERTED":
        return "DIVERTED", RED
    if delay > 5:
        return f"LATE +{delay}", RED
    if st == "BOARDING":
        return "BOARDING", GREEN
    if st == "GATECLOSED":
        return "GATE SHUT", YELLOW
    if st == "CHECKIN":
        return "CHECK-IN", CYAN
    if st in ("DEPARTED", "ARRIVED"):
        return st, scale_color(GRAY, 1.0)
    if st in ("APPROACHING", "ENROUTE"):
        return "EN ROUTE", GREEN
    return "ON TIME", GREEN


def render_flights(departures, arrivals, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)

    if not has_key:
        draw_px_centered(draw, 8, "NEED", fill=WHITE, size=PX_SMALL)
        draw_px_centered(draw, 24, "RAPIDAPI", fill=WHITE, size=PX_SMALL)
        draw_px_centered(draw, 40, "KEY", fill=WHITE, size=PX_SMALL)
        return img

    pages = [("DEP", f) for f in departures] + [("ARR", f) for f in arrivals]
    if not pages:
        draw_px_centered(draw, 2, "SFO", fill=ORANGE, size=PX_SMALL)
        draw_px_centered(draw, 28, "NO", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        draw_px_centered(draw, 40, "FLIGHTS", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    n = len(pages)
    idx = int(tick / DWELL) % n
    kind, f = pages[idx]

    head_color = ORANGE if kind == "DEP" else CYAN
    draw_px_centered(draw, 0, f"SFO {kind}", fill=head_color, size=PX_SMALL)
    filled_rect(draw, 3, 9, WIDTH - 4, 9, scale_color(head_color, 0.5))

    # flight number + city (dest for departures, origin for arrivals)
    draw_px_centered(draw, 12, _fit(str(f.get("number", "")).upper(), 10), fill=WHITE, size=PX_SMALL)
    city = str(f.get("city") or f.get("iata") or "").upper()
    draw_px_centered(draw, 22, _fit(city, 10), fill=scale_color(WHITE, 0.85), size=PX_SMALL)

    # scheduled local time + minutes-until
    t = _fmt12(str(f.get("time", "")))
    m = int(f.get("minutes", 0))
    when = t if m < 0 else (f"{t}  NOW" if m == 0 else f"{t}  {m}M")
    draw_px_centered(draw, 34, _fit(when, 11), fill=scale_color(WHITE, 0.9), size=PX_SMALL)

    # status
    label, color = _status(f)
    draw_px_centered(draw, 46, _fit(label, 10), fill=color, size=PX_SMALL)

    # paging dots (capped)
    dots = min(n, 8)
    gap = 5
    total = dots * gap - (gap - 2)
    x0 = (WIDTH - total) // 2
    for i in range(dots):
        on = i == (idx % dots)
        filled_rect(draw, x0 + i * gap, 61, x0 + i * gap + 1, 62,
                    head_color if on else scale_color(GRAY, 0.5))
    return img
