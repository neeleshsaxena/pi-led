from __future__ import annotations

import unicodedata
from datetime import datetime

from PIL import Image, ImageDraw

from pi_led_core.canvas import (
    ACCENT,
    CYAN,
    GRAY,
    GREEN,
    HEIGHT,
    PX_BIG,
    PX_HUGE,
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
    pulse_color,
    px_cap_height,
    px_text_width,
    rainbow,
    scale_color,
    sparkle,
    sweep_vbar,
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


def _draw_team_chip(draw, x0, x1, color, *, win=False, lose=False) -> None:
    """Flag-color underline under a team abbreviation. The winner gets a thicker,
    full-brightness chip; the loser a thin, muted one; undecided is the default."""
    if lose:
        filled_rect(draw, x0, 9, x1, 10, scale_color(color, 0.4))
    elif win:
        filled_rect(draw, x0, 9, x1, 11, color)  # 3px — reads as "heavier"
    else:
        filled_rect(draw, x0, 9, x1, 10, color)


def _draw_winner_tri(draw, cx, y, color) -> None:
    """Small upward triangle (5 wide) pointing up at the winning team's name."""
    draw.point((cx, y), fill=color)
    draw.line([(cx - 1, y + 1), (cx + 1, y + 1)], fill=color)
    draw.line([(cx - 2, y + 2), (cx + 2, y + 2)], fill=color)


def _draw_check(draw, x, y, color) -> None:
    """A small check mark (✓, 5 wide × 4 tall) with its bottom-left vertex low."""
    for dx, dy in ((0, 2), (1, 3), (2, 2), (3, 1), (4, 0)):
        draw.point((x + dx, y + dy), fill=color)


def _draw_winner_mark(draw, cx, y, color, *, shootout, tick) -> None:
    """The badge under the winning team's name. A team-color triangle for a
    decided-in-play final; a green ✓ when it was won on penalties — so the two
    kinds of win read differently at a glance. Gentle pulse, never strobes."""
    if shootout:
        _draw_check(draw, cx - 2, y, pulse_color(GREEN, tick, period=2.2, min_factor=0.6))
    else:
        _draw_winner_tri(draw, cx, y + 1, pulse_color(color, tick, period=2.4, min_factor=0.6))


def _draw_header(draw, home, away, home_primary, away_primary,
                 winner_side=None, shootout=False, tick=0.0) -> None:
    """Team abbreviations (kenpixel) with a full-brightness flag-color chip.

    On decided finals the winner is called out: its abbreviation stays bright
    white with a heavier chip + a marker beneath, while the loser is muted — so
    a glance lands on the winner. Live/scheduled cards (winner_side=None) are
    unchanged: both bright, plain chips."""
    home_w = px_text_width(home, PX_SMALL)
    away_w = px_text_width(away, PX_SMALL)
    home_x0 = 4
    away_x0 = WIDTH - 4 - away_w
    decided = winner_side in ("home", "away")
    home_win = winner_side == "home"
    away_win = winner_side == "away"

    home_txt = WHITE if (home_win or not decided) else scale_color(WHITE, 0.45)
    away_txt = WHITE if (away_win or not decided) else scale_color(WHITE, 0.45)
    draw_px(draw, (home_x0, 1), home, fill=home_txt, size=PX_SMALL)
    draw_px(draw, (away_x0, 1), away, fill=away_txt, size=PX_SMALL)

    _draw_team_chip(draw, home_x0, home_x0 + home_w - 1, home_primary,
                    win=home_win, lose=decided and not home_win)
    _draw_team_chip(draw, away_x0, WIDTH - 5, away_primary,
                    win=away_win, lose=decided and not away_win)

    if home_win:
        _draw_winner_mark(draw, home_x0 + home_w // 2, 13, home_primary,
                          shootout=shootout, tick=tick)
    elif away_win:
        _draw_winner_mark(draw, away_x0 + away_w // 2, 13, away_primary,
                          shootout=shootout, tick=tick)


def _pen_int(s) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def _draw_pip_col(draw, x, n, color, *, win) -> None:
    """A vertical stack of `n` 2×2 pips, centered in the hero band. The winner's
    column is full-bright; the loser's is muted — so you can literally count the
    converted penalties (e.g. 4 bright vs 3 dim) flanking the level score."""
    if n <= 0:
        return
    pitch = 3
    col = color if win else scale_color(color, 0.5)
    y0 = 27 - (n * pitch - 1) // 2
    for i in range(n):
        yy = y0 + i * pitch
        filled_rect(draw, x, yy, x + 1, yy + 1, col)


def _draw_shootout_pips(draw, match, home_c, away_c, winner_side) -> None:
    """Flank the (level) regulation score with each side's converted-penalty pips
    — home on the left, away on the right — a shape nothing else on the card has,
    so a penalty shootout reads instantly even before the eye finds the PK badge.
    Skipped for long sudden-death tallies (the numeric PK footer carries those)."""
    hp = _pen_int(match.home.pen_score)
    ap = _pen_int(match.away.pen_score)
    if hp is None or ap is None:
        return
    if max(hp, ap) > 5:  # would overflow the band — lean on the PK x-y footer
        return
    _draw_pip_col(draw, 3, hp, home_c, win=winner_side == "home")
    _draw_pip_col(draw, WIDTH - 5, ap, away_c, win=winner_side == "away")


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

    # Decided finals only: who won (incl. on penalties). Drives the header cue.
    winner_side = None
    if match.is_final:
        if match.home.winner:
            winner_side = "home"
        elif match.away.winner:
            winner_side = "away"

    # Black background + full-brightness team-color edge bars. On the LED panel
    # black = pixels off = real contrast and zero flicker; bright crisp glyphs
    # (no glow) read cleanly from across the room.
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    # team-colored edge bars with a bright highlight gliding down them (offset
    # phases so the two sides don't move in lockstep)
    sweep_vbar(draw, 0, 0, HEIGHT - 1, home_primary, tick)
    sweep_vbar(draw, WIDTH - 1, 0, HEIGHT - 1, away_primary, tick + 1.3)
    _draw_header(draw, home, away, home_primary, away_primary,
                 winner_side=winner_side, shootout=match.is_shootout, tick=tick)

    # ── hero: score or kickoff time (crisp, no glow) ──
    if is_scheduled:
        kickoff = match.kickoff_utc.astimezone(tz)
        draw_px_centered(draw, 20, kickoff.strftime("%H:%M"), fill=YELLOW, size=PX_BIG)
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
        draw_px_centered(draw, 20, score_str, fill=color, size=PX_BIG)

    # ── footer: live / HT / FT / countdown (readable font, bright) ──
    if flashing:
        _draw_goal_flash(draw, match, tick)
    elif is_halftime:
        ht = pulse_color(YELLOW, tick, period=2.0, min_factor=0.6)
        draw.ellipse([4, 38, 9, 43], fill=ht)
        draw_px(draw, (13, 38), "HT", fill=YELLOW, size=PX_SMALL)
        _draw_scorers(img, match, home_primary, away_primary, tick)
    elif match.is_live:
        dot = pulse_color(RED, tick, period=1.6, min_factor=0.6)
        draw.ellipse([4, 38, 9, 43], fill=dot)
        status_txt = (match.short_detail or match.status_label or "LIVE")[:8].upper()
        draw_px(draw, (13, 38), status_txt, fill=WHITE, size=PX_SMALL)
        _draw_scorers(img, match, home_primary, away_primary, tick)
    elif match.is_final:
        # Penalty shootout: badge "PK" + winner & pen score in their color, so a
        # level "1-1" reads clearly as decided on penalties. Otherwise "FT".
        is_so = match.is_shootout
        badge = "PK" if is_so else "FT"
        bdg_w = px_text_width(badge, PX_SMALL)
        filled_rect(draw, 4, 37, 4 + bdg_w + 3, 46, scale_color(GRAY, 0.6))
        draw_px(draw, (6, 38), badge, fill=WHITE, size=PX_SMALL)
        if is_so:
            win_home = match.home.winner
            w_abbr = home if win_home else away
            w_col = home_primary if win_home else away_primary
            hi = match.home.pen_score if win_home else match.away.pen_score
            lo = match.away.pen_score if win_home else match.home.pen_score
            draw_px(draw, (4 + bdg_w + 8, 38), f"{w_abbr} {hi}-{lo}"[:9], fill=w_col, size=PX_SMALL)
            # plus the converted-penalty pips flanking the level score above
            _draw_shootout_pips(draw, match, home_primary, away_primary, winner_side)
        else:
            tail = (match.short_detail or "").strip().upper()
            if tail and tail not in {"FT", "FULL", "FULL TIME", "FINAL"}:
                draw_px(draw, (4 + bdg_w + 8, 38), tail[:6], fill=GRAY, size=PX_SMALL)
        _draw_scorers(img, match, home_primary, away_primary, tick)
    else:
        _draw_location(img, match, tick, y=36)
        text, color = _kickoff_countdown(match, tz)
        draw_px_centered(draw, 47, text, fill=color, size=PX_SMALL)

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
    tw = px_text_width(text, PX_SMALL)
    if tw <= bw:
        draw_px(ImageDraw.Draw(img), (bx0 + (bw - tw) // 2, y), text, fill=GRAY, size=PX_SMALL)
        return
    # scroll: draw onto a band-sized strip and paste — the strip edges clip it
    strip_h = px_cap_height(PX_SMALL) + 2  # room for comma tails below the baseline
    strip = Image.new("RGB", (bw, strip_h), (0, 0, 0))
    travel = tw + bw
    off = int((tick * 16) % travel)
    draw_px(ImageDraw.Draw(strip), (bw - off, 0), text, fill=GRAY, size=PX_SMALL)
    img.paste(strip, (bx0, y))


def lerp_white(c, t: float = 0.45):
    """Lighten a team color toward white so final scores stay bright/legible."""
    return (
        int(c[0] + (255 - c[0]) * t),
        int(c[1] + (255 - c[1]) * t),
        int(c[2] + (255 - c[2]) * t),
    )


def _draw_scorers(img, match, home_c, away_c, tick, y: int = 50) -> None:
    """Ticker of EVERY scorer (both teams), each tinted by the team that scored.
    Centered & static if it all fits; otherwise it scrolls right→left, seamlessly
    looping, hard-clipped to an inner band so it never paints over the edge bars."""
    goals = sorted(list(match.home.goals) + list(match.away.goals),
                   key=lambda g: g.minute_sort_key)
    if not goals:
        return
    segs = [(_format_scorer_line(g) + "   ", home_c if g.side == "home" else away_c) for g in goals]
    widths = [micro_text_width(t) for t, _ in segs]
    total = sum(widths)
    bx0, bx1 = 3, WIDTH - 4
    bw = bx1 - bx0 + 1
    strip_h = 7

    if total <= bw:  # fits: draw centered, no scroll
        x = bx0 + (bw - total) // 2
        d = ImageDraw.Draw(img)
        for (t, c), w in zip(segs, widths):
            draw_micro(d, (x, y), t, fill=c)
            x += w
        return

    # build the full ticker once, then paste a scrolling, wrapping window of it
    strip = Image.new("RGB", (total, strip_h), (0, 0, 0))
    sd = ImageDraw.Draw(strip)
    x = 0
    for (t, c), w in zip(segs, widths):
        draw_micro(sd, (x, 0), t, fill=c)
        x += w
    off = int((tick * 14) % total)
    view = Image.new("RGB", (bw, strip_h), (0, 0, 0))
    view.paste(strip, (-off, 0))
    view.paste(strip, (total - off, 0))  # second copy fills the wrap seam
    img.paste(view, (bx0, y))


def _draw_goal_flash(draw, match, tick) -> None:
    """Celebration: confetti + a pulsing rainbow border + a bold GOAL banner.
    All bright-on-black, so it pops without flickering the whole field."""
    sparkle(draw, tick, count=18, seed=7)
    border = rainbow(tick, period=0.8)
    draw.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=border)
    goal = match.latest_goal
    side = goal.side if goal else "home"
    w = px_text_width("GOAL!", PX_SMALL)
    x = 4 if side == "home" else WIDTH - 4 - w
    draw_px(draw, (x, 50), "GOAL!", fill=pulse_color(border, tick, period=0.5, min_factor=0.7), size=PX_SMALL)


def render_empty(reason: str = "No matches") -> Image.Image:
    """Idle screen — bright logo on black so a fixtureless panel still pops."""
    img = new_canvas()
    draw = ImageDraw.Draw(img)
    filled_rect(draw, 8, 8, WIDTH - 9, 8, ACCENT)
    draw_px_centered(draw, 13, "WC", fill=ACCENT, size=PX_HUGE)
    draw_px_centered(draw, 38, "26", fill=WHITE, size=PX_BIG)
    draw_micro_centered(draw, 56, _ascii_upper(reason)[:16], fill=GRAY)
    return img
