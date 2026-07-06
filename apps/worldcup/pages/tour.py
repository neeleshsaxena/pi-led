"""World Cup knockout 'matchup tour' — one tie per slide, big flag badges.

Poster-inspired (the FIFA R16 bracket poster): two large circular flag badges, the
two country codes, and the date/score, on a dark field with a round-tinted header.
The plugin tours through the knockout ties and scrolls horizontally between these
slides (see WorldCupApp._render_tour). Lead-authored; pure rendering.
"""
from __future__ import annotations

from PIL import ImageDraw

from pi_led_core.canvas import (
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
    draw_micro_centered,
    draw_px,
    draw_px_centered,
    filled_rect,
    new_canvas,
    px_text_width,
    scale_color,
)

from .. import flags as flagmod

GOLD = (212, 170, 80)

_LABEL = {
    "round-of-32": "ROUND OF 32",
    "round-of-16": "ROUND OF 16",
    "quarterfinals": "QUARTERS",
    "semifinals": "SEMIS",
    "3rd-place-match": "3RD PLACE",
    "final": "FINAL",
}
_TINT = {
    "round-of-32": BLUE,
    "round-of-16": CYAN,
    "quarterfinals": GREEN,
    "semifinals": ORANGE,
    "3rd-place-match": PURPLE,
    "final": YELLOW,
}
_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

_FLAG_D = 26  # flag badge diameter
_CY = 26      # flag badge center y


def _code(team) -> str:
    ab = (team.short or "").strip().upper()
    return ab[:3] if ab.isalpha() else "?"


def _badge(img, team, cx: int) -> None:
    ab = (team.short or "").strip().upper()
    s = _FLAG_D
    if ab.isalpha():
        b = flagmod.flag_badge(ab, s)
        img.paste(b, (cx - s // 2, _CY - s // 2), b)
    else:  # TBD slot: dark disc with a '?'
        d = ImageDraw.Draw(img)
        x0, y0 = cx - s // 2, _CY - s // 2
        d.ellipse([x0, y0, x0 + s - 1, y0 + s - 1], fill=(40, 42, 50), outline=scale_color(GRAY, 0.6))
        draw_px(d, (cx - 2, _CY - 3), "?", fill=scale_color(GRAY, 0.85), size=PX_SMALL)


def _px_centered_at(d, cx: int, y: int, text: str, fill) -> int:
    w = px_text_width(text, PX_SMALL)
    draw_px(d, (cx - w // 2, y), text, fill=fill, size=PX_SMALL)
    return w


def _status(m, tz):
    if m.is_final:
        s = f"{m.home.score or '0'}-{m.away.score or '0'}"
        if m.is_shootout:
            s += " PK"
        return s, WHITE
    if m.is_live:
        return (m.short_detail or m.status_label or "LIVE")[:9].upper(), YELLOW
    dt = m.kickoff_utc.astimezone(tz)
    return f"{_MON[dt.month - 1]} {dt.day}", scale_color(GRAY, 0.85)


def render_slide(slug, m, idx, total, tz, tick=0.0):
    img = new_canvas()
    d = ImageDraw.Draw(img)
    tint = _TINT.get(slug, GOLD)

    # header
    draw_px_centered(d, 1, _LABEL.get(slug, "KNOCKOUT"), fill=tint, size=PX_SMALL)
    filled_rect(d, 10, 9, WIDTH - 11, 9, scale_color(tint, 0.5))

    # flag badges + a small gold 'v' between them
    _badge(img, m.home, 16)
    _badge(img, m.away, 48)
    draw_micro_centered(d, _CY - 2, "V", fill=scale_color(GOLD, 0.9))

    # codes — winner pops white, loser dims; a gold underline marks the winner
    decided = m.is_final
    h_win = decided and m.home.winner
    a_win = decided and m.away.winner
    h_col = WHITE if (not decided or h_win) else scale_color(GRAY, 0.5)
    a_col = WHITE if (not decided or a_win) else scale_color(GRAY, 0.5)
    hw = _px_centered_at(d, 16, 42, _code(m.home), h_col)
    aw = _px_centered_at(d, 48, 42, _code(m.away), a_col)
    if h_win:
        filled_rect(d, 16 - hw // 2, 50, 16 - hw // 2 + hw - 1, 50, GOLD)
    if a_win:
        filled_rect(d, 48 - aw // 2, 50, 48 - aw // 2 + aw - 1, 50, GOLD)

    # date / score
    text, col = _status(m, tz)
    draw_micro_centered(d, 54, text, fill=col)

    # progress through the tour
    if total > 1:
        w = WIDTH - 8
        fillw = max(1, int(round(w * (idx + 1) / total)))
        filled_rect(d, 4, 62, WIDTH - 5, 62, scale_color(GRAY, 0.3))
        filled_rect(d, 4, 62, 4 + fillw - 1, 62, tint)
    return img


def render_empty(reason: str = "no ties yet"):
    img = new_canvas()
    d = ImageDraw.Draw(img)
    draw_px_centered(d, 20, "KNOCKOUT", fill=GOLD, size=PX_SMALL)
    draw_micro_centered(d, 36, reason.upper()[:16], fill=GRAY)
    return img
