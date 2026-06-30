"""Knockout bracket — TREE view. One bracket node per screen: a focus tie on the
right with its two feeder matches on the left, joined by bracket connector lines,
so the progression reads as a real tree (feeders → winner advances → focus tie).

The plugin walks the enabled rounds and feeds one (focus, feederA, feederB) cell
at a time. This is only used when two+ knockout rounds are enabled; with a single
round the plugin renders the per-round list (bracket.py) instead.

Lead-authored sibling of bracket.py (the per-round list). Pure rendering — shares
its visual language (flag-color chips, per-round title tint, winner pops/loser
dims, TBD dash). See deploy/UI-UX-WORKSTREAM.md for ownership.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    BLUE,
    CYAN,
    GRAY,
    GREEN,
    ORANGE,
    PURPLE,
    PX_SMALL,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro,
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_cap_height,
    scale_color,
)

from ..teams import colors_for

_LABELS = {
    "round-of-32": "ROUND OF 32",
    "round-of-16": "ROUND OF 16",
    "quarterfinals": "QUARTERS",
    "semifinals": "SEMIS",
    "3rd-place-match": "3RD PLACE",
    "final": "FINAL",
}
# Cool -> gold ramp, warming toward the FINAL (matches bracket.py).
_TINT = {
    "round-of-32": BLUE,
    "round-of-16": CYAN,
    "quarterfinals": GREEN,
    "semifinals": ORANGE,
    "3rd-place-match": PURPLE,
    "final": YELLOW,
}


def _disp(team) -> tuple[str, bool]:
    ab = (team.short or "").strip().upper()
    if ab and ab.isalpha():
        return ab[:3], True
    return "—", False


def _row_color(real: bool, decided: bool, win: bool, primary):
    if not real:
        return scale_color(GRAY, 0.45)
    if decided:
        return primary if win else scale_color(GRAY, 0.6)
    return scale_color(WHITE, 0.9)


def _feeder(draw, x: int, top: int, m, tz) -> None:
    """Compact 2-row feeder match ('ABV S' per team, winner colored). None = TBD."""
    if m is None:
        draw_micro(draw, (x, top + 4), "TBD", fill=scale_color(GRAY, 0.5))
        return
    decided = m.is_final
    for r, team in enumerate((m.home, m.away)):
        y = top + r * 8
        disp, real = _disp(team)
        win = decided and team.winner
        primary, _ = colors_for(disp) if real else (GRAY, GRAY)
        col = _row_color(real, decided, win, primary)
        draw_micro(draw, (x, y), disp, fill=col)
        if decided or m.is_live:
            sc = (team.score or "0")
            if m.is_shootout and win:
                sc += "p"
            draw_micro(draw, (x + 15, y), sc, fill=col)


def _focus(draw, x: int, m, tz) -> None:
    """Focus tie at right: 2 teams (PX_SMALL) with flag chips, score/date below."""
    decided = m.is_final
    ch = px_cap_height(PX_SMALL)
    for r, team in enumerate((m.home, m.away)):
        y = 24 + r * 9
        disp, real = _disp(team)
        win = decided and team.winner
        primary, _ = colors_for(disp) if real else (GRAY, GRAY)
        draw_px(draw, (x, y), disp, fill=_row_color(real, decided, win, primary), size=PX_SMALL)
        if real and (win or not decided):
            chip = primary
        elif real:
            chip = scale_color(primary, 0.35)
        else:
            chip = scale_color(GRAY, 0.3)
        filled_rect(draw, WIDTH - 2, y, WIDTH - 1, y + ch - 1, chip)
    if decided or m.is_live:
        mid = f"{(m.home.score or '0')}-{(m.away.score or '0')}"
        if m.is_shootout:
            mid += "p"
        mcol = YELLOW if m.is_live else WHITE
    else:
        dt = m.kickoff_utc.astimezone(tz)
        mid = f"{dt.month}/{dt.day}"
        mcol = scale_color(GRAY, 0.7)
    draw_micro(draw, (x, 44), mid, fill=mcol)


def _connectors(draw, tint) -> None:
    """Bracket lines: each feeder's exit converges to a junction, then into focus."""
    c = scale_color(tint, 0.6)
    y_a, y_b, x_join, x_focus = 17, 45, 33, 41
    draw.line([(24, y_a), (x_join, y_a)], fill=c)
    draw.line([(24, y_b), (x_join, y_b)], fill=c)
    draw.line([(x_join, y_a), (x_join, y_b)], fill=c)
    draw.line([(x_join, (y_a + y_b) // 2), (x_focus, (y_a + y_b) // 2)], fill=c)


def _dots(draw, round_idx: int, round_count: int, tint) -> None:
    if round_count <= 1:
        return
    gap = 6
    total = round_count * gap - (gap - 3)
    sx = (WIDTH - total) // 2
    y = 61
    for i in range(round_count):
        x = sx + i * gap
        if i == round_idx:
            filled_rect(draw, x, y, x + 2, y + 2, tint)
        else:
            draw.point((x + 1, y + 1), fill=scale_color(GRAY, 0.8))


def render(slug, focus, feeder_a, feeder_b, round_idx, round_count, cell_idx, cell_count, tz, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    tint = _TINT.get(slug, ACCENT)
    draw_px_centered(draw, 1, _LABELS.get(slug, slug.replace("-", " ").upper()), fill=tint, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(tint, 0.55))
    _feeder(draw, 2, 13, feeder_a, tz)
    _feeder(draw, 2, 41, feeder_b, tz)
    _connectors(draw, tint)
    _focus(draw, 42, focus, tz)
    _dots(draw, round_idx, round_count, tint)
    return img


def render_empty(reason: str = "no bracket yet"):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 20, "BRACKET", fill=ACCENT, size=PX_SMALL)
    draw_micro_centered(draw, 36, reason.upper()[:16], fill=GRAY)
    return img
