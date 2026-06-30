from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .espn import ESPNClient
from .pages import matches as matches_page
from .pages import standings as standings_page
from .standings import StandingsClient

LOCAL_TZ = datetime.now().astimezone().tzinfo or ZoneInfo("UTC")
PAGE_HOLD_SECONDS = float(os.environ.get("LED_PAGE_HOLD", "5.0"))
GOAL_FLASH_SECONDS = float(os.environ.get("LED_GOAL_FLASH", "3.0"))
# If this view hasn't rendered for longer than this (the carousel was showing
# something else), restart pagination on return so it always begins at match 1.
AWAY_GAP_SECONDS = float(os.environ.get("LED_WC_AWAY_GAP", "2.0"))


class WorldCupApp(LedApp):
    """World Cup on the panel. Three admin-selectable views:
    today's matches, next match-day's matches, and group standings. The plugin
    owns rotation through the day's matches / groups and the goal-flash pulse —
    logic that lived in match-day-live's LED runner before the panel was shared."""

    id = "worldcup"
    name = "World Cup"

    def __init__(self) -> None:
        self.tz = LOCAL_TZ
        self.espn: ESPNClient | None = None
        self.standings: StandingsClient | None = None
        self._page_idx = 0
        self._last_rotate = 0.0
        self._last_view: str | None = None
        self._last_render_tick = 0.0
        self._score_cache: dict[str, tuple[str, str]] = {}
        self._goal_flash_until: dict[str, float] = {}

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="today", label="Matches Today"),
            ViewSpec(id="next", label="Next Scheduled"),
            ViewSpec(id="standings", label="WC Standings"),
        ]

    async def start(self) -> None:
        # Lazily created here so the web process (which never calls start())
        # doesn't spin up unused HTTP clients.
        self.espn = ESPNClient()
        self.standings = StandingsClient()

    async def aclose(self) -> None:
        if self.espn:
            await self.espn.close()
        if self.standings:
            await self.standings.close()

    def _reset_rotation(self, tick: float) -> None:
        self._page_idx = 0
        self._last_rotate = tick

    def _maybe_rotate(self, count: int, tick: float) -> None:
        if count <= 1:
            self._page_idx = 0
            return
        if tick - self._last_rotate >= PAGE_HOLD_SECONDS:
            self._page_idx = (self._page_idx + 1) % count
            self._last_rotate = tick

    def _update_goal_flashes(self, day_matches, tick: float) -> None:
        for m in day_matches:
            cur = (m.home.score or "0", m.away.score or "0")
            prev = self._score_cache.get(m.id)
            self._score_cache[m.id] = cur
            if prev is not None and prev != cur and m.is_live:
                self._goal_flash_until[m.id] = tick + GOAL_FLASH_SECONDS

    async def _render_matches(self, mode: str, tick: float) -> Image.Image:
        snapshot = await self.espn.get()
        # "today" -> today's matches; "next" -> the next match-day's matches
        # (i.e. up to one day out, in kickoff order).
        day_matches = matches_page.pick_day_matches(snapshot, mode, self.tz)
        if not day_matches:
            return matches_page.render_empty("no fixtures")
        self._update_goal_flashes(day_matches, tick)
        self._maybe_rotate(len(day_matches), tick)
        idx = self._page_idx % len(day_matches)
        current = day_matches[idx]
        flash_remaining = max(0.0, self._goal_flash_until.get(current.id, 0.0) - tick)
        return matches_page.render(
            current,
            self.tz,
            idx,
            len(day_matches),
            tick=tick,
            goal_flash_remaining=flash_remaining,
        )

    async def _render_standings(self, tick: float) -> Image.Image:
        snapshot = await self.standings.get()
        groups = snapshot.groups
        if not groups:
            return standings_page.render_empty()
        self._maybe_rotate(len(groups), tick)
        idx = self._page_idx % len(groups)
        return standings_page.render(groups[idx], idx, len(groups), tick=tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        """Tell the carousel how long to dwell here: PAGE_HOLD per match, so every
        match in the view is shown once before the carousel moves on. Uses the
        cached snapshot (no network); returns None (carousel default) until the
        cache warms or when there are no fixtures."""
        if self.espn is None or view_id == "standings":
            return None
        snap = self.espn.cached()
        if snap is None:
            return None
        mode = "next" if view_id == "next" else "today"
        n = len(matches_page.pick_day_matches(snap, mode, self.tz))
        return n * PAGE_HOLD_SECONDS if n > 0 else None

    async def render(self, ctx: RenderContext) -> Image.Image:
        gap = ctx.tick - self._last_render_tick
        self._last_render_tick = ctx.tick
        # Reset pagination on a view change OR when returning after being off-
        # screen (the carousel was elsewhere), so a view always starts at match 1.
        if ctx.view != self._last_view or gap > AWAY_GAP_SECONDS:
            self._reset_rotation(ctx.tick)
            self._last_view = ctx.view
        if ctx.view == "standings":
            return await self._render_standings(ctx.tick)
        # "today" / "next" (and any unknown view defaults to today)
        mode = "next" if ctx.view == "next" else "today"
        return await self._render_matches(mode, ctx.tick)
