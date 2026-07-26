"""Plant watering reminder — pixel rendering (UI-owned).

One group per frame (indoor / outdoor): a big days-until-water number, a gentle
status line, and a potted plant whose mood tracks how thirsty it is — perky with
a little bloom when it's happy, softly drooping when it wants a drink. Outdoor
frames show a rain-cloud + "RAIN-FED" when recent rain reset the clock.

Everything but the plant itself carries a per-group color identity: indoor is a
warm magenta/pink "grow-light" theme, outdoor a cool cyan/blue "night sky" theme —
label + sweeping underline, twinkling accents, tinted water droplets, a purple/blue
"N DAYS LEFT" accent, a rainbow "RAIN-FED" flourish. The plant (pot/soil/leaves/
bloom) stays the same mood-driven green/olive regardless of group. No background
wash — a colored fill behind the pixel font read badly on the real HUB75 panel.

Deliberately gentle: no alarm-red, no "OVERDUE!" — an overdue plant just looks a
little thirsty and asks nicely, in warm amber. Entry point:
    render_group(group, remaining, interval, rain_fed, tick)
`remaining` = interval - days_since_watered (>0 days left, 0 due today, <0 past).
"""
from __future__ import annotations

import math

from PIL import ImageDraw

from pi_led_core.canvas import (
    BLUE,
    CYAN,
    GREEN,
    LIME,
    MAGENTA,
    PINK,
    PURPLE,
    PX_BIG,
    PX_HUGE,
    PX_SMALL,
    WHITE,
    WIDTH,
    YELLOW,
    draw_micro_centered,
    draw_px_centered,
    filled_rect,
    lerp_color,
    new_canvas,
    pulse_color,
    rainbow,
    scale_color,
    sparkle,
    sweep_hbar,
)

# Per-group color identity for everything except the plant itself: header label
# + underline, twinkles, and the water droplet/raincloud tint. Indoor reads warm
# (grow-light magenta/pink); outdoor reads cool (night-sky cyan/blue) — a glance
# at the color alone tells you which group is on screen. (No background wash —
# a colored fill behind the pixel font read badly on the actual HUB75 panel.)
GROUP_THEME = {
    "indoor": {
        "label": MAGENTA,
        "underline": PINK,
        "sparkle": (MAGENTA, PINK, PURPLE),
        "water": (255, 132, 188),   # warm rosy droplet
        "happy": PURPLE,            # "N DAYS LEFT" number/status when plenty of time is left
    },
    "outdoor": {
        "label": CYAN,
        "underline": BLUE,
        "sparkle": (BLUE, CYAN, WHITE),
        "water": (92, 196, 255),    # cool sky droplet
        "happy": BLUE,
    },
}

# Soft, warm palette — nothing alarm-red. A thirsty plant reads as amber/olive.
# (This part IS the plant — pot/soil/leaves/bloom — and stays the same regardless
# of group; only the water droplet's tint comes from GROUP_THEME above.)
POT = (198, 108, 66)          # terracotta
POT_HI = (226, 138, 96)       # sunlit side of the pot
SOIL = (96, 60, 40)
LEAF = (66, 206, 104)         # healthy green
LEAF_DRY = (150, 168, 92)     # thirsty: desaturated olive
AMBER = (240, 172, 78)        # gentle "needs a drink" accent (not red)
BLOOM = (255, 138, 180)       # flower petals
BLOOM_C = (255, 214, 96)      # flower center
SKY = (168, 190, 216)


# ── plant (mood-aware) ────────────────────────────────────────────────────────

# Leaf offsets from the soil surface: (dx, dy, radius). Happy leaves reach up and
# out; thirsty leaves sag lower and outward. dy is negative = above the soil.
_LEAVES = {
    "happy":   [(-6, -4, 3), (6, -5, 3), (-4, -9, 3), (4, -10, 3), (0, -13, 4)],
    "ok":      [(-6, -3, 3), (6, -4, 3), (-4, -7, 3), (4, -8, 3), (0, -11, 3)],
    "due":     [(-6, -3, 3), (6, -4, 3), (-4, -7, 3), (4, -8, 3), (0, -11, 3)],
    "thirsty": [(-7, 1, 3), (7, 0, 3), (-6, -3, 3), (6, -4, 3), (0, -6, 3)],
}


def _pot(draw, cx: int, by: int) -> int:
    """Terracotta pot with bottom at y=by. Returns the soil-surface y."""
    top = by - 7
    draw.polygon([(cx - 8, top), (cx + 8, top), (cx + 6, by), (cx - 6, by)], fill=POT)
    draw.line([(cx - 7, top + 1), (cx - 5, by - 1)], fill=POT_HI)          # sunlit edge
    filled_rect(draw, cx - 9, top - 2, cx + 9, top - 1, POT_HI)            # rim
    filled_rect(draw, cx - 7, top, cx + 7, top, SOIL)                      # soil
    return top


def _plant(draw, cx: int, by: int, mood: str, tick: float, water_color) -> None:
    """A charming potted plant whose posture reflects `mood`."""
    sy = _pot(draw, cx, by)
    color = LEAF_DRY if mood == "thirsty" else LEAF
    leaves = _LEAVES[mood]
    # stem
    stem_top = sy + (min(dy for _, dy, _ in leaves)) + 2
    if mood == "thirsty":
        draw.line([(cx, sy), (cx - 1, stem_top)], fill=scale_color(color, 0.9))  # slight wilt
    else:
        draw.line([(cx, sy), (cx, stem_top)], fill=scale_color(color, 0.9))
    # leaves (gentle sway; the higher a leaf, the more it drifts)
    sway = math.sin(tick * 1.3) * 1.0
    for dx, dy, r in leaves:
        drift = int(round(sway * (1.0 if dy < -5 else 0.4)))
        lx, ly = cx + dx + drift, sy + dy
        draw.ellipse([lx - r, ly - 2, lx + r, ly + 2], fill=color)
        draw.point((lx, ly - 1), fill=scale_color(color, 1.3))  # sheen
    if mood == "happy":
        # a little bloom crowns a happy plant (with a soft twinkle)
        ty = sy - 15
        for a in range(0, 360, 72):
            px = cx + int(round(math.cos(math.radians(a)) * 2))
            py = ty + int(round(math.sin(math.radians(a)) * 2))
            draw.point((px, py), fill=BLOOM)
        draw.point((cx, ty), fill=pulse_color(BLOOM_C, tick, period=1.6, min_factor=0.7))
    if mood == "due":
        # a single droplet drifts down toward the soil — "ready for a drink"
        dy = int((tick * 12) % 22)
        _droplet(draw, cx, sy - 18 + dy, water_color)


def _droplet(draw, x: int, y: int, color) -> None:
    draw.polygon([(x, y - 3), (x - 2, y + 1), (x + 2, y + 1)], fill=color)
    draw.ellipse([x - 2, y, x + 2, y + 3], fill=color)


def _raincloud(draw, x: int, y: int, tick: float, tint, water_color) -> None:
    cloud = lerp_color(SKY, tint, 0.35)
    draw.ellipse([x - 6, y - 3, x + 6, y + 3], fill=cloud)
    draw.ellipse([x - 3, y - 5, x + 4, y + 2], fill=scale_color(cloud, 1.2))
    for i, dx in enumerate(range(-4, 5, 3)):
        off = int((tick * 10 + i * 3) % 6)
        draw.line([(x + dx, y + 4 + off), (x + dx, y + 6 + off)], fill=water_color)


# ── view ──────────────────────────────────────────────────────────────────────


def _mood(remaining: int):
    """Map days-left to (mood, accent color, gentle status word)."""
    if remaining < 0:
        return "thirsty", AMBER, "THIRSTY"
    if remaining == 0:
        return "due", YELLOW, "WATER TODAY"
    if remaining <= 2:
        return "ok", LIME, "WATER SOON"
    return "happy", GREEN, ("DAYS LEFT" if remaining != 1 else "DAY LEFT")


def render_group(group, remaining, interval, rain_fed, tick=0.0):
    theme = GROUP_THEME[group]
    img = new_canvas()
    draw = ImageDraw.Draw(img)

    label = "OUTDOOR" if group == "outdoor" else "INDOOR"
    draw_px_centered(draw, 1, label, fill=theme["label"], size=PX_SMALL)
    sweep_hbar(draw, 6, WIDTH - 7, 9, theme["underline"], tick, period=3.0, band=16, hi=0.9)
    sparkle(draw, tick, count=5, seed=(1 if group == "indoor" else 2),
            colors=theme["sparkle"], box=(2, 0, WIDTH - 2, 8))

    mood, accent, status = _mood(remaining)
    if mood == "happy":
        accent = theme["happy"]  # group-tinted instead of flat green (blends into the plant otherwise)
    num = str(remaining)
    # thirsty number breathes softly in warm amber — a gentle nudge, never a klaxon
    num_col = pulse_color(AMBER, tick, period=1.8, min_factor=0.62) if mood == "thirsty" else accent
    one = len(num) == 1
    draw_px_centered(draw, 12 if one else 15, num, fill=num_col, size=PX_HUGE if one else PX_BIG)
    draw_px_centered(draw, 35, status, fill=scale_color(accent, 0.95), size=PX_SMALL)

    _plant(draw, WIDTH // 2, 63, mood, tick, theme["water"])

    if group == "outdoor" and rain_fed:
        _raincloud(draw, WIDTH - 12, 20, tick, theme["underline"], theme["water"])
        draw_micro_centered(draw, 45, "RAIN-FED", fill=rainbow(tick, period=2.5))
    return img
