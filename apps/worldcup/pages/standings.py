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
    draw_hline,
    draw_text,
    filled_rect,
    font_small,
    new_canvas,
    pulse_color,
    scale_color,
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
    font = font_small()

    letter = _group_letter(group)

    label = "GROUP"
    label_w = text_width(draw, label, font)
    letter_w = big_text_width(letter, scale=2)
    gap = 4
    total_w = label_w + gap + letter_w
    start_x = (WIDTH - total_w) // 2
    draw_text(draw, (start_x, 4), label, fill=scale_color(ACCENT, 0.55), font=font)
    letter_color = pulse_color(ACCENT, tick, period=2.4, min_factor=0.65, max_factor=1.0)
    draw_big(draw, (start_x + label_w + gap, 0), letter, fill=letter_color, scale=2)

    draw_hline(draw, 16, fill=DIM)

    base_y = 19
    row_h = 9
    for i, e in enumerate(group.entries[:4]):
        rank = i + 1
        y = base_y + i * row_h

        if rank <= 2:
            badge = GREEN
            text_color = WHITE
        elif rank == 3:
            badge = YELLOW
            text_color = WHITE
        else:
            badge = scale_color(RED, 0.85)
            text_color = GRAY

        filled_rect(draw, 0, y, 1, y + row_h - 2, badge)
        draw_text(draw, (4, y), str(rank), fill=text_color, font=font)
        team = (e.team_short or e.team_name[:3]).upper()[:3]
        draw_text(draw, (12, y), team, fill=text_color, font=font)

        if e.played:
            wd = f"W{e.wins}"
            wd_w = text_width(draw, wd, font)
            draw_text(draw, (WIDTH - wd_w - 14, y), wd, fill=scale_color(text_color, 0.55), font=font)

        pts = str(e.points)
        pts_w = text_width(draw, pts, font)
        pts_color = badge if rank <= 2 else text_color
        draw_text(draw, (WIDTH - pts_w - 3, y), pts, fill=pts_color, font=font)

    if page_count > 1:
        dot_y = 60
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
            lbl = f"{page_idx + 1}/{page_count}"
            draw_centered(draw, dot_y - 4, lbl, fill=GRAY)

    return img


def render_empty() -> Image.Image:
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    draw_big_centered(draw, 18, "?", fill=ACCENT, scale=2)
    draw_centered(draw, 42, "no groups", fill=GRAY)
    return img
