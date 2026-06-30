"""Knockout bracket page — one round of matchups per screen, winners highlighted.

Owned by the UI/UX workstream (pure rendering). The plugin groups the knockout
matches by round and paginates them (see WorldCupApp._render_bracket); this just
draws one page: a round title + up to a handful of matchup rows + round dots.

Each row is  HOME   score/date   AWAY  — the winner is drawn in its team color,
the loser dimmed; undecided ties show the kickoff date; teams not yet determined
(TBD) show a dim dash. See deploy/UI-UX-WORKSTREAM.md for ownership.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    GRAY,
    PX_SMALL,
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

from ..espn import Match
from ..teams import colors_for

# ESPN season.slug -> short, panel-friendly round title.
_LABELS = {
    "round-of-32": "ROUND OF 32",
    "round-of-16": "ROUND OF 16",
    "quarterfinals": "QUARTERS",
    "semifinals": "SEMIS",
    "3rd-place-match": "3RD PLACE",
    "final": "FINAL",
}

_ROW_Y0 = 12
_ROW_PITCH = 10


def _disp(team) -> tuple[str, bool]:
    """(abbrev, is_real). TBD/placeholder slots (RD32, QFW1, SF L1 ...) carry
    digits/spaces in their 'abbreviation'; real FIFA codes are 3 letters."""
    ab = (team.short or "").strip().upper()
    if ab and ab.isalpha():
        return ab[:3], True
    return "—", False  # em dash = team not yet determined


def _team_color(real: bool, decided: bool, win: bool, primary):
    if not real:
        return scale_color(GRAY, 0.45)       # TBD
    if decided:
        return primary if win else scale_color(GRAY, 0.6)  # winner pops, loser dims
    return scale_color(WHITE, 0.9)           # known team, tie not played yet


def _draw_row(draw, y: int, m: Match, tz) -> None:
    h_disp, h_real = _disp(m.home)
    a_disp, a_real = _disp(m.away)
    decided = m.is_final
    h_primary, _ = colors_for(h_disp) if h_real else (GRAY, GRAY)
    a_primary, _ = colors_for(a_disp) if a_real else (GRAY, GRAY)

    draw_px(draw, (2, y), h_disp,
            fill=_team_color(h_real, decided, m.home.winner, h_primary), size=PX_SMALL)
    aw = px_text_width(a_disp, PX_SMALL)
    draw_px(draw, (WIDTH - 2 - aw, y), a_disp,
            fill=_team_color(a_real, decided, m.away.winner, a_primary), size=PX_SMALL)

    if decided or m.is_live:
        mid = f"{(m.home.score or '0')}-{(m.away.score or '0')}"
        if m.is_shootout:
            mid += "p"  # decided on penalties
        mcol = YELLOW if m.is_live else WHITE
    else:
        dt = m.kickoff_utc.astimezone(tz)
        mid = f"{dt.month}/{dt.day}"
        mcol = scale_color(GRAY, 0.7)
    mw = micro_text_width(mid)
    draw_micro(draw, ((WIDTH - mw) // 2, y + 1), mid, fill=mcol)


def _draw_round_dots(draw, round_idx: int, round_count: int) -> None:
    """One dot per knockout round; the current round is the bright accent dot."""
    if round_count <= 1:
        return
    gap = 6
    total_w = round_count * gap - (gap - 3)
    start_x = (WIDTH - total_w) // 2
    y = 61
    for i in range(round_count):
        x = start_x + i * gap
        if i == round_idx:
            filled_rect(draw, x, y, x + 2, y + 2, ACCENT)
        else:
            draw.point((x + 1, y + 1), fill=GRAY)


def render(slug, matches, round_idx, round_count, page_idx, page_count, tz, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    label = _LABELS.get(slug, slug.replace("-", " ").upper())
    draw_px_centered(draw, 1, label, fill=ACCENT, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(ACCENT, 0.5))
    for i, m in enumerate(matches):
        _draw_row(draw, _ROW_Y0 + i * _ROW_PITCH, m, tz)
    _draw_round_dots(draw, round_idx, round_count)
    return img


def render_empty(reason: str = "no bracket yet"):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 20, "BRACKET", fill=ACCENT, size=PX_SMALL)
    draw_micro_centered(draw, 36, reason.upper()[:16], fill=GRAY)
    return img
