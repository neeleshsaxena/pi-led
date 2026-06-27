from __future__ import annotations

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    DIM,
    GRAY,
    GREEN,
    RED,
    WHITE,
    WIDTH,
    YELLOW,
    big_text_width,
    draw_big,
    draw_big_centered,
    draw_centered,
    draw_text,
    filled_rect,
    font_small,
    new_canvas,
    scale_color,
    sweep_hbar,
    text_width,
)

from ..standings import StandingsGroup


def _group_letter(group: StandingsGroup) -> str:
    raw = (group.short or group.name or "?").strip()
    letter = raw.replace("Group ", "").replace("GROUP ", "").strip() or "?"
    return letter[:1].upper()


def render(
    group: StandingsGroup,
    page_idx: int = 0,
    page_count: int = 12,
    tick: float = 0.0,
) -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)

    # Header: "GROUP X" in bold, with a full-brightness accent rule beneath.
    letter = _group_letter(group)
    draw_big(draw, (4, 2), "GROUP", fill=WHITE, scale=1)
    lx = WIDTH - 4 - big_text_width(letter, 2)
    draw_big(draw, (lx, 0), letter, fill=ACCENT, scale=2)
    sweep_hbar(draw, 0, WIDTH - 1, 13, ACCENT, tick)

    base_y = 17
    row_h = 11
    font = font_small()
    for i, e in enumerate(group.entries[:4]):
        rank = i + 1
        y = base_y + i * row_h

        if rank <= 2:        # advance
            badge, text_color = GREEN, WHITE
        elif rank == 3:      # playoff
            badge, text_color = YELLOW, WHITE
        else:                # out
            badge, text_color = RED, GRAY

        # chunky full-brightness rank badge down the left edge
        filled_rect(draw, 0, y, 2, y + 8, badge)
        draw_big(draw, (5, y + 1), str(rank), fill=text_color, scale=1)
        team = (e.team_short or e.team_name[:3]).upper()[:3]
        draw_big(draw, (12, y + 1), team, fill=text_color, scale=1)

        # right edge: points (bold, badge-colored); a compact win count sits
        # just to its left with a clear gap so nothing overlaps the team.
        pts = str(e.points)
        pts_w = big_text_width(pts, 1)
        draw_big(draw, (WIDTH - 4 - pts_w, y + 1), pts,
                 fill=badge if rank <= 3 else text_color, scale=1)
        if e.played:
            wd = f"{e.wins}W"
            wd_w = text_width(draw, wd, font)
            draw_text(draw, (WIDTH - 8 - pts_w - wd_w, y + 1), wd,
                      fill=scale_color(text_color, 0.5), font=font)

    _draw_pager(draw, page_idx, page_count)
    return img


def _draw_pager(draw, page_idx, page_count) -> None:
    if page_count <= 1:
        return
    dot_y = 61
    if page_count * 4 + 4 <= WIDTH:
        total_w = page_count * 4 - 2
        start_x = (WIDTH - total_w) // 2
        for i in range(page_count):
            x = start_x + i * 4
            if i == page_idx:
                filled_rect(draw, x, dot_y, x + 2, dot_y + 2, ACCENT)
            else:
                draw.point((x + 1, dot_y + 1), fill=DIM)
    else:
        draw_centered(draw, dot_y - 1, f"{page_idx + 1}/{page_count}", fill=GRAY)


def render_empty() -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    filled_rect(draw, 8, 9, WIDTH - 9, 9, ACCENT)
    draw_big_centered(draw, 18, "?", fill=ACCENT, scale=3)
    draw_centered(draw, 44, "no groups", fill=GRAY)
    return img
