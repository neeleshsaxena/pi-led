"""Premier League — pixel rendering (functional scaffold; UI polish TBD).

Three views:
  - render_scores   : today's / live matches, one card at a time (score + minute).
  - render_fixtures : upcoming matches, one card at a time (teams + kickoff).
  - render_table    : the league table, ~6 rows a page, paging through all 20.

Team abbreviations are tinted with each club's colour. Kickoff times are shown in
the panel's local timezone. See deploy/UI-ASKS.md — layouts are UI-owned polish.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GRAY,
    GREEN,
    ORANGE,
    PX_BIG,
    PX_SMALL,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    micro_text_width,
    new_canvas,
    px_cap_height,
    px_text_width,
    scale_color,
)

FAV = YELLOW  # highlight colour for the favorite team


def _star(draw, cx: int, cy: int, color=FAV) -> None:
    """A tiny sparkle-star marker."""
    for p in ((cx, cy - 2), (cx, cy - 1), (cx, cy + 1), (cx, cy + 2),
              (cx - 2, cy), (cx - 1, cy), (cx + 1, cy), (cx + 2, cy), (cx, cy)):
        draw.point(p, fill=color)


def _underline(draw, x0: int, y_top: int, width: int, color=FAV) -> None:
    yy = y_top + px_cap_height(PX_BIG) + 1
    filled_rect(draw, x0, yy, x0 + max(0, width - 1), yy, color)

_LOCAL = ZoneInfo("America/Los_Angeles")
_DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_PAGE = 4.0  # seconds per paged card / table page


def _team_color(hexstr: str):
    h = (hexstr or "").lstrip("#")
    if len(h) != 6:
        return WHITE
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return WHITE
    mx = max(r, g, b)
    if mx < 40:  # near-black kit (e.g. Newcastle 000000) — invisible on black; use light gray
        return (205, 205, 212)
    if mx < 120:  # dark but colored — scale up preserving hue (multiplying keeps the tint)
        f = 120.0 / mx
        r, g, b = min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f))
    return (r, g, b)


def _hhmm(dt: datetime | None) -> str:
    if not dt:
        return ""
    lt = dt.astimezone(_LOCAL)
    ap = "A" if lt.hour < 12 else "P"
    return f"{lt.hour % 12 or 12}:{lt.minute:02d}{ap}"


def _daydate(dt: datetime | None) -> str:
    if not dt:
        return ""
    lt = dt.astimezone(_LOCAL)
    return f"{_DOW[lt.weekday()]} {lt.month}/{lt.day}"


def _dots(draw, idx: int, n: int, color=ACCENT) -> None:
    if n <= 1:
        return
    n = min(n, 10)
    gap = 5
    x0 = (WIDTH - (n * gap - (gap - 2))) // 2
    for i in range(n):
        on = i == (idx % n)
        filled_rect(draw, x0 + i * gap, 61, x0 + i * gap + 1, 62, color if on else scale_color(GRAY, 0.5))


def _side(draw, y: int, side: dict, show_score: bool, fav: bool = False) -> None:
    abbr = str(side.get("abbr", "")).upper()[:4] or "?"
    draw_px(draw, (2, y), abbr, fill=_team_color(side.get("color", "")), size=PX_BIG)
    if fav:
        _underline(draw, 2, y, px_text_width(abbr, PX_BIG))
    if show_score:
        s = str(side.get("score", 0))
        draw_px(draw, (WIDTH - px_text_width(s, PX_BIG) - 2, y), s, fill=WHITE, size=PX_BIG)


def _is_fav(side: dict, fav: str) -> bool:
    return bool(fav) and str(side.get("abbr", "")).upper() == fav


def render_scores(matches, tick=0.0, favorite=""):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px(draw, (1, 0), "EPL", fill=ACCENT, size=PX_SMALL)
    if not matches:
        draw_px_centered(draw, 22, "NO GAMES", fill=scale_color(WHITE, 0.75), size=PX_SMALL)
        draw_px_centered(draw, 36, "TODAY", fill=scale_color(WHITE, 0.6), size=PX_SMALL)
        return img

    n = len(matches)
    idx = int(tick / _PAGE) % n
    m = matches[idx]
    home, away = m.get("home", {}), m.get("away", {})
    fav_h, fav_a = _is_fav(home, favorite), _is_fav(away, favorite)
    state = m.get("state")
    if state == "in":
        stat, col = (m.get("clock") or "LIVE"), RED
    elif state == "post":
        stat, col = "FT", scale_color(GRAY, 1.0)
    else:
        stat, col = _hhmm(m.get("date")), CYAN
    draw_px(draw, (WIDTH - px_text_width(stat, PX_SMALL) - 1, 0), stat, fill=col, size=PX_SMALL)
    if fav_h or fav_a:  # your team is playing — star by the header
        _star(draw, px_text_width("EPL", PX_SMALL) + 6, 3)
    filled_rect(draw, 1, 9, WIDTH - 2, 9, scale_color(ACCENT, 0.4))

    played = state in ("in", "post")
    _side(draw, 14, home, played, fav=fav_h)
    _side(draw, 34, away, played, fav=fav_a)
    _dots(draw, idx, n)
    return img


def _center_abbr(draw, y: int, abbr: str, color, fav: bool) -> None:
    abbr = str(abbr or "?")[:4]
    w = px_text_width(abbr, PX_BIG)
    x0 = (WIDTH - w) // 2
    draw_px(draw, (x0, y), abbr, fill=color, size=PX_BIG)
    if fav:
        _underline(draw, x0, y, w)


def render_fixtures(matches, tick=0.0, favorite=""):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 0, "UPCOMING", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 3, 9, WIDTH - 4, 9, scale_color(ACCENT, 0.4))
    if not matches:
        draw_px_centered(draw, 28, "NO FIXTURES", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    n = len(matches)
    idx = int(tick / _PAGE) % n
    m = matches[idx]
    home, away = m.get("home", {}), m.get("away", {})
    fav_h, fav_a = _is_fav(home, favorite), _is_fav(away, favorite)
    if fav_h or fav_a:
        _star(draw, WIDTH - 6, 3)
    _center_abbr(draw, 13, home.get("abbr", "?"), _team_color(home.get("color", "")), fav_h)
    draw_micro_centered(draw, 30, "VS", fill=scale_color(GRAY, 0.9))
    _center_abbr(draw, 37, away.get("abbr", "?"), _team_color(away.get("color", "")), fav_a)
    when = f"{_daydate(m.get('date'))}  {_hhmm(m.get('date'))}".strip()
    draw_micro_centered(draw, 54, when, fill=scale_color(WHITE, 0.85))
    _dots(draw, idx, n)
    return img


def _rank_color(rank: int, total: int):
    if 1 <= rank <= 4:
        return GREEN          # Champions League places
    if rank == 5:
        return ORANGE         # Europa
    if total >= 18 and rank >= total - 2:
        return RED            # relegation zone
    return scale_color(WHITE, 0.85)


def render_table(rows, tick=0.0, favorite=""):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 0, "EPL TABLE", fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 3, 9, WIDTH - 4, 9, scale_color(ACCENT, 0.4))
    if not rows:
        draw_px_centered(draw, 28, "NO TABLE", fill=scale_color(WHITE, 0.7), size=PX_SMALL)
        return img

    per = 6
    total = len(rows)
    pages = (total + per - 1) // per
    # If a favorite is set, park the table on its page so their row is always the
    # one on screen (still cycles other pages so the rest is visible too).
    fav_page = next((k // per for k, r in enumerate(rows)
                     if favorite and str(r.get("abbr", "")).upper() == favorite), None)
    order = ([fav_page] + [p for p in range(pages) if p != fav_page]) if fav_page is not None else list(range(pages))
    pg = order[int(tick / (_PAGE * 1.5)) % len(order)]
    chunk = rows[pg * per:pg * per + per]
    for i, r in enumerate(chunk):
        y = 11 + i * 8
        rank = int(r.get("rank", 0))
        is_fav = bool(favorite) and str(r.get("abbr", "")).upper() == favorite
        if is_fav:  # highlight your team's row
            filled_rect(draw, 0, y - 1, WIDTH - 1, y + 6, scale_color(FAV, 0.20))
            _star(draw, WIDTH - 4, y + 3)
        draw_px(draw, (1, y), str(rank), fill=_rank_color(rank, total), size=PX_SMALL)
        draw_px(draw, (14, y), str(r.get("abbr", ""))[:4], fill=FAV if is_fav else WHITE, size=PX_SMALL)
        gd = int(r.get("gd", 0))
        gd_s = f"{'+' if gd > 0 else ''}{gd}"
        draw_micro_centered(draw, y + 1, gd_s, fill=scale_color(GRAY, 0.9), x0=37, x1=49)
        pts = str(int(r.get("points", 0)))
        draw_px(draw, (WIDTH - px_text_width(pts, PX_SMALL) - (7 if is_fav else 1), y), pts,
                fill=ACCENT, size=PX_SMALL)
    _dots(draw, order.index(pg), pages)
    return img
