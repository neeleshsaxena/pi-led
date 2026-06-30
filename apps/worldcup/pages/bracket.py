"""Knockout bracket page — one round of matchups per screen, winners highlighted.

Owned by the UI/UX workstream (pure rendering). The plugin groups the knockout
matches by round and paginates them (see WorldCupApp._render_bracket); this just
draws one page: a round title + up to a handful of matchup rows + round dots.

Each row is  ▌HOME   score/date   AWAY▐  — both teams carry a flag-color chip on
their edge, the winner pops in its team color (with an underline) while the loser
dims; undecided ties show the kickoff date; TBD teams show a dim dash. The round
title is tinted on a cool→gold ramp that warms as you near the FINAL, so each
round reads as a distinct rung. See deploy/UI-UX-WORKSTREAM.md for ownership.
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
    micro_text_width,
    new_canvas,
    px_cap_height,
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

# Per-round title tint — a cool→gold ramp that warms as the bracket converges on
# the FINAL, so each rung looks distinct and "later = hotter".
_ROUND_TINT = {
    "round-of-32": BLUE,
    "round-of-16": CYAN,
    "quarterfinals": GREEN,
    "semifinals": ORANGE,
    "3rd-place-match": PURPLE,
    "final": YELLOW,
}

_ROW_Y0 = 12
_ROW_PITCH = 10
_CHIP_W = 2


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


def _chip(draw, x: int, y: int, ch: int, primary, *, real: bool, decided: bool, win: bool) -> None:
    """A team flag-color chip on the row edge. Full brightness for the winner /
    any undecided team; dimmed for a loser; faint for a TBD slot."""
    if not real:
        color = scale_color(GRAY, 0.3)
    elif decided and not win:
        color = scale_color(primary, 0.35)
    else:
        color = primary
    filled_rect(draw, x, y, x + _CHIP_W - 1, y + ch - 1, color)


def _draw_row(draw, y: int, m: Match, tz) -> None:
    h_disp, h_real = _disp(m.home)
    a_disp, a_real = _disp(m.away)
    decided = m.is_final
    h_win = decided and m.home.winner
    a_win = decided and m.away.winner
    h_primary, _ = colors_for(h_disp) if h_real else (GRAY, GRAY)
    a_primary, _ = colors_for(a_disp) if a_real else (GRAY, GRAY)
    ch = px_cap_height(PX_SMALL)

    # edge chips in each team's flag color
    _chip(draw, 0, y, ch, h_primary, real=h_real, decided=decided, win=h_win)
    _chip(draw, WIDTH - _CHIP_W, y, ch, a_primary, real=a_real, decided=decided, win=a_win)

    # team abbreviations (winner pops in its color, loser dims, TBD dash)
    hx = _CHIP_W + 2
    h_col = _team_color(h_real, decided, m.home.winner, h_primary)
    draw_px(draw, (hx, y), h_disp, fill=h_col, size=PX_SMALL)
    aw = px_text_width(a_disp, PX_SMALL)
    ax = WIDTH - _CHIP_W - 2 - aw
    a_col = _team_color(a_real, decided, m.away.winner, a_primary)
    draw_px(draw, (ax, y), a_disp, fill=a_col, size=PX_SMALL)

    # underline the advancing team in its color (a clear "through to next round" cue)
    if h_win:
        filled_rect(draw, hx, y + ch, hx + px_text_width(h_disp, PX_SMALL) - 1, y + ch, h_primary)
    if a_win:
        filled_rect(draw, ax, y + ch, ax + aw - 1, y + ch, a_primary)

    # center: score (decided/live) or kickoff date (scheduled)
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


def _draw_round_dots(draw, round_idx: int, round_count: int, tint) -> None:
    """One dot per knockout round; the current round is the bright round-tint dot."""
    if round_count <= 1:
        return
    gap = 6
    total_w = round_count * gap - (gap - 3)
    start_x = (WIDTH - total_w) // 2
    y = 61
    for i in range(round_count):
        x = start_x + i * gap
        if i == round_idx:
            filled_rect(draw, x, y, x + 2, y + 2, tint)
        else:
            draw.point((x + 1, y + 1), fill=scale_color(GRAY, 0.8))


def render(slug, matches, round_idx, round_count, page_idx, page_count, tz, tick=0.0):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    tint = _ROUND_TINT.get(slug, ACCENT)
    label = _LABELS.get(slug, slug.replace("-", " ").upper())
    draw_px_centered(draw, 1, label, fill=tint, size=PX_SMALL)
    filled_rect(draw, 6, 9, WIDTH - 7, 9, scale_color(tint, 0.55))
    # vertically center the matchup block in the content band so sparse rounds
    # (a lone FINAL / 3rd-place tie) sit centered instead of floating up top.
    n = len(matches)
    band_top, band_bot = _ROW_Y0, 59
    block_h = (n - 1) * _ROW_PITCH + px_cap_height(PX_SMALL) if n else 0
    y0 = band_top + max(0, ((band_bot - band_top) - block_h) // 2)
    for i, m in enumerate(matches):
        _draw_row(draw, y0 + i * _ROW_PITCH, m, tz)
    _draw_round_dots(draw, round_idx, round_count, tint)
    return img


def render_empty(reason: str = "no bracket yet"):
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_px_centered(draw, 20, "BRACKET", fill=ACCENT, size=PX_SMALL)
    draw_micro_centered(draw, 36, reason.upper()[:16], fill=GRAY)
    return img
