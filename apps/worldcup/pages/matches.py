from __future__ import annotations

import unicodedata
from datetime import datetime

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GLYPH_H,
    GRAY,
    HEIGHT,
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
    pulse_color,
    rainbow,
    scale_color,
    sparkle,
    sweep_vbar,
    text_width,
)

from ..espn import Match, Snapshot
from ..teams import colors_for


def pick_day_matches(snapshot: Snapshot, mode: str, tz) -> list[Match]:
    """mode is "today" or "next"."""
    today_key = datetime.now(tz).strftime("%Y-%m-%d")
    buckets: dict[str, list[Match]] = {}
    for m in snapshot.matches:
        local_key = m.kickoff_utc.astimezone(tz).strftime("%Y-%m-%d")
        buckets.setdefault(local_key, []).append(m)

    if mode == "next":
        future = sorted(d for d in buckets if d > today_key)
        return buckets[future[0]] if future else []

    if today_key in buckets:
        return buckets[today_key]
    future = sorted(d for d in buckets if d > today_key)
    return buckets[future[0]] if future else []


def _short(label: str | None, fallback: str = "—") -> str:
    s = (label or fallback).strip().upper()
    return s[:3] if s else fallback


def _kickoff_countdown(match: Match, tz) -> tuple[str, tuple[int, int, int]]:
    from datetime import timezone as _tz
    now = datetime.now(_tz.utc)
    delta = match.kickoff_utc - now
    secs = int(delta.total_seconds())
    if secs <= 0:
        return ("KICKOFF", YELLOW)
    if secs < 60:
        return ("STARTING", YELLOW)
    if secs < 60 * 60:
        return (f"IN {secs // 60}M", YELLOW)
    if secs < 24 * 60 * 60:
        hours = secs // 3600
        mins = (secs % 3600) // 60
        if mins == 0:
            return (f"IN {hours}H", CYAN)
        return (f"IN {hours}H {mins}M", CYAN)
    days = secs // (24 * 60 * 60)
    return (f"IN {days}D", CYAN)


_HALFTIME = "STATUS_HALFTIME"
_MAX_SCORER_CHARS = 11


def _ascii_upper(s: str) -> str:
    norm = unicodedata.normalize("NFKD", s)
    stripped = "".join(c for c in norm if not unicodedata.combining(c))
    return stripped.upper()


def _format_scorer_line(goal) -> str:
    minute = (goal.minute or "").replace("'", "").strip()[:5]
    raw = goal.player or ""
    surname = raw.split(".")[-1].strip() if "." in raw else raw.split(" ")[-1].strip()
    name = _ascii_upper(surname)
    max_name = max(3, _MAX_SCORER_CHARS - len(minute) - 1)
    return f"{minute} {name[:max_name]}".strip()


def _draw_header(draw, home, away, home_primary, away_primary) -> None:
    """Team abbreviations (bold 5x7) with a full-brightness flag-color chip."""
    home_w = big_text_width(home, 1)
    away_w = big_text_width(away, 1)
    draw_big(draw, (4, 1), home, fill=WHITE, scale=1)
    draw_big(draw, (WIDTH - 4 - away_w, 1), away, fill=WHITE, scale=1)
    filled_rect(draw, 4, 9, 4 + home_w - 1, 10, home_primary)
    filled_rect(draw, WIDTH - 4 - away_w, 9, WIDTH - 5, 10, away_primary)


def _draw_pager(draw, page_idx, page_count) -> None:
    if page_count <= 1:
        return
    dot_y = 61
    gap = 5
    total_w = page_count * gap - 2
    start_x = (WIDTH - total_w) // 2
    for i in range(page_count):
        x = start_x + i * gap
        if i == page_idx:
            filled_rect(draw, x, dot_y, x + 2, dot_y + 2, ACCENT)
        else:
            draw.point((x + 1, dot_y + 1), fill=GRAY)


def render(
    match: Match,
    tz,
    page_idx: int = 0,
    page_count: int = 1,
    tick: float = 0.0,
    goal_flash_remaining: float = 0.0,
) -> Image.Image:
    home = _short(match.home.short or match.home.name)
    away = _short(match.away.short or match.away.name)
    home_primary, _ = colors_for(home)
    away_primary, _ = colors_for(away)

    is_scheduled = not (match.is_live or match.is_final)
    is_halftime = match.status_raw == _HALFTIME
    flashing = goal_flash_remaining > 0

    # Black background + full-brightness team-color edge bars. On the LED panel
    # black = pixels off = real contrast and zero flicker; bright crisp glyphs
    # (no glow) read cleanly from across the room.
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    # team-colored edge bars with a bright highlight gliding down them (offset
    # phases so the two sides don't move in lockstep)
    sweep_vbar(draw, 0, 0, HEIGHT - 1, home_primary, tick)
    sweep_vbar(draw, WIDTH - 1, 0, HEIGHT - 1, away_primary, tick + 1.3)
    _draw_header(draw, home, away, home_primary, away_primary)

    # ── hero: score or kickoff time (crisp, no glow) ──
    if is_scheduled:
        kickoff = match.kickoff_utc.astimezone(tz)
        draw_big_centered(draw, 20, kickoff.strftime("%H:%M"), fill=YELLOW, scale=2)
    else:
        home_s = (match.home.score or "0")[:2]
        away_s = (match.away.score or "0")[:2]
        score_str = f"{home_s}-{away_s}"
        if flashing:
            color = rainbow(tick, period=1.0)
        elif is_halftime:
            color = YELLOW
        elif match.is_live:
            color = WHITE
        else:  # final — bright (FT badge marks it done), faintly leading-team tinted
            if home_s > away_s:
                color = lerp_white(home_primary)
            elif away_s > home_s:
                color = lerp_white(away_primary)
            else:
                color = scale_color(WHITE, 0.9)
        draw_big_centered(draw, 20, score_str, fill=color, scale=2)

    # ── footer: live / HT / FT / countdown (readable font, bright) ──
    if flashing:
        _draw_goal_flash(draw, match, tick)
    elif is_halftime:
        ht = pulse_color(YELLOW, tick, period=2.0, min_factor=0.6)
        draw.ellipse([4, 38, 9, 43], fill=ht)
        draw_big(draw, (13, 37), "HT", fill=YELLOW, scale=1)
        _draw_scorer(draw, match)
    elif match.is_live:
        dot = pulse_color(RED, tick, period=1.6, min_factor=0.6)
        draw.ellipse([4, 38, 9, 43], fill=dot)
        status_txt = (match.short_detail or match.status_label or "LIVE")[:8].upper()
        draw_big(draw, (13, 37), status_txt, fill=WHITE, scale=1)
        _draw_scorer(draw, match)
    elif match.is_final:
        ft_w = big_text_width("FT", 1)
        filled_rect(draw, 4, 37, 4 + ft_w + 3, 45, scale_color(GRAY, 0.6))
        draw_big(draw, (6, 38), "FT", fill=WHITE, scale=1)
        tail = (match.short_detail or "").strip().upper()
        if tail and tail not in {"FT", "FULL", "FULL TIME", "FINAL"}:
            draw_big(draw, (4 + ft_w + 8, 38), tail[:6], fill=GRAY, scale=1)
        _draw_scorer(draw, match)
    else:
        _draw_location(img, match, tick, y=36)
        text, color = _kickoff_countdown(match, tz)
        draw_big_centered(draw, 47, text, fill=color, scale=1)

    _draw_pager(draw, page_idx, page_count)
    return img


def _draw_location(img, match, tick, y: int = 36) -> None:
    """Stadium/venue line for scheduled cards, in the readable 5x7 font. Centers
    if it fits; otherwise scrolls right→left, hard-clipped to a safe inner band
    so it never paints over the team edge bars. (Scheduled cards only — live/
    final cards use that lower band for the scorer line.)"""
    venue = _ascii_upper((match.venue or "").strip())
    city = _ascii_upper((match.city or "").strip())   # "City, State"
    text = "  -  ".join(p for p in (venue, city) if p)
    if not text:
        return
    bx0, bx1 = 4, WIDTH - 5
    bw = bx1 - bx0 + 1
    tw = big_text_width(text, 1)
    if tw <= bw:
        draw_big(ImageDraw.Draw(img), (bx0 + (bw - tw) // 2, y), text, fill=GRAY, scale=1)
        return
    # scroll: draw onto a band-sized strip and paste — the strip edges clip it
    strip = Image.new("RGB", (bw, GLYPH_H), (0, 0, 0))
    travel = tw + bw
    off = int((tick * 16) % travel)
    draw_big(ImageDraw.Draw(strip), (bw - off, 0), text, fill=GRAY, scale=1)
    img.paste(strip, (bx0, y))


def lerp_white(c, t: float = 0.45):
    """Lighten a team color toward white so final scores stay bright/legible."""
    return (
        int(c[0] + (255 - c[0]) * t),
        int(c[1] + (255 - c[1]) * t),
        int(c[2] + (255 - c[2]) * t),
    )


def _draw_scorer(draw, match) -> None:
    goal = match.latest_goal
    if not goal:
        return
    line = _format_scorer_line(goal)
    font = font_small()
    w = text_width(draw, line, font)
    x = 4 if goal.side == "home" else WIDTH - 4 - w
    draw_text(draw, (x, 49), line, fill=scale_color(WHITE, 0.8), font=font)


def _draw_goal_flash(draw, match, tick) -> None:
    """Celebration: confetti + a pulsing rainbow border + a bold GOAL banner.
    All bright-on-black, so it pops without flickering the whole field."""
    sparkle(draw, tick, count=18, seed=7)
    border = rainbow(tick, period=0.8)
    draw.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=border)
    goal = match.latest_goal
    side = goal.side if goal else "home"
    w = big_text_width("GOAL!", 1)
    x = 4 if side == "home" else WIDTH - 4 - w
    draw_big(draw, (x, 50), "GOAL!", fill=pulse_color(border, tick, period=0.5, min_factor=0.7), scale=1)


def render_empty(reason: str = "No matches") -> Image.Image:
    """Idle screen — bright logo on black so a fixtureless panel still pops."""
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    filled_rect(draw, 8, 8, WIDTH - 9, 8, ACCENT)
    draw_big_centered(draw, 13, "WC", fill=ACCENT, scale=3)
    draw_big_centered(draw, 35, "26", fill=WHITE, scale=2)
    draw_centered(draw, 51, reason[:11], fill=GRAY)
    return img
