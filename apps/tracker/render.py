"""Flight-tracker — pixel rendering (UI-owned).

One screen for a whole journey: the itinerary (origin → … → destination) with the
current position highlighted, the destination arrival time as the hero (coloured
by delay), the active leg's status, and a countdown until it lands.

Entry point: render_tracker(label, legs, status, now, has_key, tick). `legs` is the
config list (`{number,date,from,to,dep_local,arr_local,dep_utc,arr_utc}`); `status`
maps flight number -> the live dict from TrackerClient.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GRAY,
    GREEN,
    MICRO_H,
    PX_BIG,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
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


def _iso(s) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _done(status: str) -> bool:
    s = (status or "").lower()
    return any(k in s for k in ("arriv", "land"))


def _state(status: str) -> tuple[str, tuple]:
    """(short label, colour) for a leg/flight status string."""
    s = (status or "").lower()
    if "cancel" in s:
        return "CANCELLED", RED
    if "divert" in s:
        return "DIVERTED", RED
    if _done(s):
        return "LANDED", GREEN
    if "enroute" in s or "en route" in s or "airborne" in s or "departed" in s:
        return "IN AIR", CYAN
    if "board" in s:
        return "BOARDING", YELLOW
    if "delay" in s:
        return "DELAYED", RED
    return "SCHEDULED", scale_color(WHITE, 0.8)


def _delay_color(mins: int):
    if mins <= 5:
        return GREEN
    if mins <= 20:
        return YELLOW
    return RED


def _plane(draw, x: int, y: int, color) -> None:
    """A tiny 7x5 plane pointing right."""
    filled_rect(draw, x, y + 2, x + 5, y + 2, color)       # fuselage
    draw.point((x + 6, y + 2), fill=color)                 # nose
    filled_rect(draw, x + 2, y, x + 3, y + 4, color)       # wings
    draw.point((x, y), fill=color)                         # tail
    draw.point((x, y + 4), fill=color)


def _countdown(target: datetime | None, now: datetime) -> str:
    if not target:
        return ""
    secs = (target - now).total_seconds()
    if secs <= 0:
        return "ARRIVING"
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"IN {d}D {h}H"
    if h:
        return f"IN {h}H {m:02d}M"
    return f"IN {m}M"


def _route(draw, y: int, legs: list, dones: list, focus_idx: int, started: bool) -> None:
    """Origin → … → destination across the top: airports already reached are green,
    the one being flown toward is cyan, the rest dim."""
    codes = ([str(legs[0].get("from", "")).upper()] +
             [str(l.get("to", "")).upper() for l in legs])
    seg = [micro_text_width(c, spacing=1) for c in codes]
    aw = micro_text_width(">", spacing=1)
    total = sum(seg) + (aw + 4) * (len(codes) - 1)
    x = max(1, (WIDTH - total) // 2)
    for i, c in enumerate(codes):
        if i == 0:
            col = scale_color(GREEN, 0.9) if started else scale_color(WHITE, 0.85)
        elif dones[i - 1]:
            col = scale_color(GREEN, 0.9)              # arrival airport of a finished leg
        elif (i - 1) == focus_idx:
            col = CYAN                                 # flying toward this one now
        else:
            col = scale_color(WHITE, 0.6)
        draw_micro(draw, (x, y), c, fill=col, spacing=1)
        x += seg[i]
        if i < len(codes) - 1:
            x += 2
            draw_micro(draw, (x, y), ">", fill=scale_color(GRAY, 0.7), spacing=1)
            x += aw + 2


def render_tracker(label, legs, status, now=None, has_key=True, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    now = now or datetime.now(timezone.utc)

    dest = (str(legs[-1].get("to", "")).upper() if legs else "") or "DEST"
    head = (str(label).upper().strip() or f"TO {dest}")
    _plane(draw, 2, 1, ACCENT)
    draw_px(draw, (11, 0), head, fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 1, 9, WIDTH - 2, 9, scale_color(ACCENT, 0.45))

    if not has_key:
        draw_px_centered(draw, 26, "NEED", fill=WHITE, size=PX_SMALL)
        draw_px_centered(draw, 38, "ADB KEY", fill=WHITE, size=PX_SMALL)
        return img
    if not legs:
        draw_px_centered(draw, 30, "NO TRIP", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    def _num(l):
        return str(l.get("number", "")).upper()

    def leg_done(l):
        st = status.get(_num(l), {})
        if _done(st.get("status", "")):
            return True
        a = _iso(l.get("arr_utc"))
        return bool(a and now > a)   # past scheduled arrival with no feed => treat as landed

    dones = [leg_done(l) for l in legs]
    # Focus = the leg in progress: the last leg if the whole trip is done, else the
    # first not-yet-done leg.
    focus_idx = (len(legs) - 1) if dones[-1] else next((i for i, d in enumerate(dones) if not d), len(legs) - 1)
    started = dones[0] or bool(status.get(_num(legs[0])))
    last, last_st = legs[-1], status.get(_num(legs[-1]), {})
    focus, focus_st = legs[focus_idx], status.get(_num(legs[focus_idx]), {})

    _route(draw, 12, legs, dones, focus_idx, started)

    # Hero: destination arrival time, coloured by delay (green once landed).
    arr = last_st.get("arr", {}) if isinstance(last_st, dict) else {}
    arr_hhmm = arr.get("est_hhmm") or arr.get("sched_hhmm") or str(last.get("arr_local", "")) or "--:--"
    delay = int(arr.get("delay_min", 0) or 0)
    landed = dones[-1]
    hero_col = GREEN if landed else _delay_color(delay)
    draw_px(draw, ((WIDTH - px_text_width(arr_hhmm, PX_BIG)) // 2, 20), arr_hhmm, fill=hero_col, size=PX_BIG)

    # Status line: focus flight number + its state.
    if landed or leg_done(focus):
        st_txt, st_col = "LANDED", GREEN
    elif focus_st.get("status"):
        st_txt, st_col = _state(focus_st["status"])
    elif now < (_iso(focus.get("dep_utc")) or now):
        st_txt, st_col = "SCHEDULED", scale_color(WHITE, 0.8)
    else:
        st_txt, st_col = "IN AIR", CYAN
    draw_micro_centered(draw, 40, f"{_num(focus)}  {st_txt}", fill=st_col)

    # Footer: delay or countdown to arrival.
    if landed:
        foot, fcol = "LANDED", GREEN
    elif delay > 0:
        foot, fcol = f"+{delay} MIN", _delay_color(delay)
    else:
        foot, fcol = (_countdown(arr.get("est_utc") or _iso(last.get("arr_utc")), now) or "ON TIME"), GREEN
    draw_px_centered(draw, 50, foot, fill=fcol, size=PX_SMALL)
    return img
