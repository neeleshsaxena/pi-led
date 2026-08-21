"""Premier League board — scores, fixtures, and the league table.

Modeled on the old World Cup app but for a league (ESPN eng.1, keyless). Three
views: live/today scores, upcoming fixtures, and the standings table. Data/config/
lifecycle live here (lead-owned); pixel layout lives in render.py (UI-owned).

Config: `league` (an ESPN soccer league id, default "eng.1"). Point it at another
league (e.g. "esp.1", "ger.1") and the same three views work.
"""
from __future__ import annotations

import os

from PIL import Image

from pi_led_core.plugin import LedApp, RenderContext, ViewSpec

from .espn import EplClient
from .render import render_fixtures, render_scores, render_table

DEFAULT_LEAGUE = "eng.1"


def _fav_first(matches: list[dict], fav: str) -> list[dict]:
    """Float the favorite team's matches to the front (stable: keeps date order
    within each group)."""
    if not fav:
        return matches
    return sorted(
        matches,
        key=lambda m: fav not in (m.get("home", {}).get("abbr", ""), m.get("away", {}).get("abbr", "")),
    )


class EplApp(LedApp):
    id = "epl"
    name = "Premier League"

    def __init__(self) -> None:
        self.client: EplClient | None = None
        self._league = DEFAULT_LEAGUE
        self._scores: list[dict] = []
        self._fixtures: list[dict] = []
        self._table: list[dict] = []

    def views(self) -> list[ViewSpec]:
        return [
            ViewSpec(id="scores", label="EPL Scores"),
            ViewSpec(id="fixtures", label="EPL Fixtures"),
            ViewSpec(id="table", label="EPL Table"),
        ]

    def default_config(self) -> dict:
        # `favorite`: club abbreviation (e.g. "CHE") to prioritize + highlight.
        # Generic (empty) in the repo; the real pick lives in the stored config.
        return {"league": DEFAULT_LEAGUE, "favorite": os.environ.get("EPL_FAVORITE", "")}

    async def start(self) -> None:
        self.client = EplClient(self._league)

    async def aclose(self) -> None:
        if self.client:
            await self.client.close()

    def _ensure_client(self, cfg: dict) -> None:
        league = str(cfg.get("league", DEFAULT_LEAGUE)) or DEFAULT_LEAGUE
        if self.client is None or league != self._league:
            self._league = league
            self.client = EplClient(league)

    async def render(self, ctx: RenderContext) -> Image.Image:
        cfg = ctx.config or {}
        self._ensure_client(cfg)
        view = ctx.view
        try:
            if view == "fixtures":
                fresh = await self.client.upcoming()
                if fresh:
                    self._fixtures = fresh
            elif view == "table":
                fresh = await self.client.standings()
                if fresh:
                    self._table = fresh
            else:  # scores (today/live)
                self._scores = await self.client.scoreboard()  # [] = genuinely no matches
        except Exception:  # noqa: BLE001 - best-effort; keep last-good
            pass

        fav = str(cfg.get("favorite", "")).upper()
        if view == "fixtures":
            return render_fixtures(_fav_first(self._fixtures, fav), ctx.tick, favorite=fav)
        if view == "table":
            return render_table(self._table, ctx.tick, favorite=fav)
        return render_scores(_fav_first(self._scores, fav), ctx.tick, favorite=fav)

    def view_cycle_seconds(self, view_id: str, config: dict) -> float | None:
        # Each view pages internally; give the carousel time to show several.
        return {"scores": 14.0, "fixtures": 16.0, "table": 20.0}.get(view_id, 14.0)
