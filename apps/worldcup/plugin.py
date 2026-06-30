from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .espn import ESPNClient, group_knockout
from .pages import bracket as bracket_page
from .pages import bracket_tree
from .pages import matches as matches_page
from .pages import standings as standings_page
from .standings import StandingsClient

LOCAL_TZ = datetime.now().astimezone().tzinfo or ZoneInfo("UTC")
PAGE_HOLD_SECONDS = float(os.environ.get("LED_PAGE_HOLD", "5.0"))
GOAL_FLASH_SECONDS = float(os.environ.get("LED_GOAL_FLASH", "3.0"))
# If this view hasn't rendered for longer than this (the carousel was showing
# something else), restart pagination on return so it always begins at match 1.
AWAY_GAP_SECONDS = float(os.environ.get("LED_WC_AWAY_GAP", "2.0"))
# Matchups shown per bracket page (a round with more than this paginates).
BRACKET_PER_PAGE = int(os.environ.get("LED_BRACKET_PER_PAGE", "3"))
# Per-page hold for the bracket view — intentionally longer than PAGE_HOLD_SECONDS
# so viewers have time to read 3 matchups. Does NOT affect match/standings rotation.
BRACKET_HOLD = float(os.environ.get("LED_BRACKET_HOLD", "7"))
# Knockout rounds the bracket view shows, smallest set first. Defaults to just
# the round of 32 — enable later rounds (in the worldcup config's bracket_rounds)
# once R32 wraps. With one round it renders the per-round list; with two+ it
# renders the converging tree.
DEFAULT_BRACKET_ROUNDS = [r.strip() for r in os.environ.get("LED_BRACKET_ROUNDS", "round-of-32").split(",") if r.strip()]


def _is_real(team) -> bool:
    """A determined team (real 3-letter FIFA code) vs a TBD placeholder."""
    return (team.short or "").strip().isalpha()


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
        self._grp_idx = 0          # standings group rotation, persists across visits
        self._grp_rotate = 0.0
        self._brk_idx = 0          # bracket page rotation, persists across visits
        self._brk_rotate = 0.0
        self._last_view: str | None = None
        self._last_render_tick = 0.0
        self._score_cache: dict[str, tuple[str, str]] = {}
        self._goal_flash_until: dict[str, float] = {}

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="today", label="Matches Today"),
            ViewSpec(id="next", label="Next Scheduled"),
            ViewSpec(id="bracket", label="Knockout Bracket"),
            ViewSpec(id="standings", label="WC Standings"),
        ]

    def default_config(self) -> dict:
        # Which knockout rounds the bracket view shows. Start with R32 only;
        # add "round-of-16", "quarterfinals", "semifinals", "final" once R32 wraps.
        return {"bracket_rounds": list(DEFAULT_BRACKET_ROUNDS)}

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
        # Pull the COMPLETE scorer list for the visible match (the scoreboard
        # feed's goal details are partial). Cached per event: 20s while live,
        # ~1h once final (finished goals don't change).
        if current.is_live or current.is_final:
            try:
                current.home.goals, current.away.goals = await self.espn.goals_for(
                    current, ttl=(20.0 if current.is_live else 3600.0)
                )
            except Exception:  # noqa: BLE001 - scorer enrichment is best-effort
                pass
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
        # Standings keeps its OWN rotation that persists across carousel visits —
        # there are far more groups than fit one dwell, so this cycles through all
        # of them over successive visits instead of always restarting at group 1.
        if self._grp_rotate == 0.0:
            self._grp_rotate = tick
        elif len(groups) > 1 and tick - self._grp_rotate >= PAGE_HOLD_SECONDS:
            self._grp_idx = (self._grp_idx + 1) % len(groups)
            self._grp_rotate = tick
        idx = self._grp_idx % len(groups)
        return standings_page.render(groups[idx], idx, len(groups), tick=tick)

    def _enabled_rounds(self, snapshot, config) -> list[tuple[str, list]]:
        """Knockout rounds (slug, matches) the bracket should show, per the
        bracket_rounds config — in bracket order, only those that exist."""
        wanted = config.get("bracket_rounds") or DEFAULT_BRACKET_ROUNDS
        wanted = set(wanted)
        return [(slug, ms) for slug, ms in group_knockout(snapshot.matches) if slug in wanted]

    def _feeder_for(self, team, prev_matches):
        """The previous-round match this (determined) team won — its feeder in the
        tree. None if the team is TBD or no completed feeder is found."""
        if not _is_real(team):
            return None
        tid = team.team_id
        for pm in prev_matches:
            if (pm.home.winner and pm.home.team_id == tid) or (pm.away.winner and pm.away.team_id == tid):
                return pm
        return None

    def _bracket_cells(self, rounds) -> list[tuple]:
        """Tree cells: each next-round tie + its two feeder matches. Only emitted
        for rounds that have a previous enabled round, and skipping all-TBD ties."""
        cells: list[tuple] = []
        for i in range(1, len(rounds)):
            slug, matches = rounds[i]
            prev = rounds[i - 1][1]
            for m in matches:
                fa, fb = self._feeder_for(m.home, prev), self._feeder_for(m.away, prev)
                if _is_real(m.home) or _is_real(m.away) or fa or fb:
                    cells.append((slug, m, fa, fb, i, len(rounds)))
        return cells

    def _bracket_list_pages(self, rounds) -> list[tuple]:
        pages: list[tuple] = []
        for ri, (slug, matches) in enumerate(rounds):
            for i in range(0, len(matches), BRACKET_PER_PAGE):
                pages.append((slug, matches[i:i + BRACKET_PER_PAGE], ri, len(rounds)))
        return pages

    def _advance_brk(self, count: int, tick: float, hold: float = PAGE_HOLD_SECONDS) -> int:
        """Persistent rotation index across carousel visits (like standings).
        `hold` lets callers use a view-specific dwell (e.g. BRACKET_HOLD)
        without affecting the shared PAGE_HOLD_SECONDS used elsewhere."""
        if self._brk_rotate == 0.0:
            self._brk_rotate = tick
        elif count > 1 and tick - self._brk_rotate >= hold:
            self._brk_idx = (self._brk_idx + 1) % count
            self._brk_rotate = tick
        return self._brk_idx % count

    async def _render_bracket(self, tick: float, config: dict) -> Image.Image:
        snapshot = await self.espn.get()
        rounds = self._enabled_rounds(snapshot, config)
        if not rounds:
            return bracket_page.render_empty()
        # Two+ enabled rounds -> converging tree; a single round -> per-round list.
        cells = self._bracket_cells(rounds) if len(rounds) >= 2 else []
        if cells:
            idx = self._advance_brk(len(cells), tick, hold=BRACKET_HOLD)
            slug, focus, fa, fb, ri, rc = cells[idx]
            return bracket_tree.render(slug, focus, fa, fb, ri, rc, idx, len(cells), self.tz, tick=tick)
        pages = self._bracket_list_pages(rounds)
        if not pages:
            return bracket_page.render_empty()
        idx = self._advance_brk(len(pages), tick, hold=BRACKET_HOLD)
        slug, matches, ri, rc = pages[idx]
        return bracket_page.render(slug, matches, ri, rc, idx, len(pages), self.tz, tick=tick)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        """Tell the carousel how long to dwell on the match views: PAGE_HOLD per
        match, so every match is shown once before the carousel moves on. Uses the
        cached snapshot (no network); None means the carousel default dwell.
        Standings is left at the default — it rotates its many groups across
        visits (see _render_standings) rather than in one long block."""
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
        if ctx.view == "bracket":
            return await self._render_bracket(ctx.tick, ctx.config or {})
        # "today" / "next" (and any unknown view defaults to today)
        mode = "next" if ctx.view == "next" else "today"
        return await self._render_matches(mode, ctx.tick)
