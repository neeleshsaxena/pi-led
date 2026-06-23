"""Thin ESPN scoreboard client for the LED worldcup plugin.

Self-contained copy (slight duplication with match-day-live's web app is by
design — the panel must keep working independently). Trimmed to what the LED
pages actually use: match cards + latest-goal line. The web-app-only bits
(per-event summary scorers, broadcasts, venue extras) are omitted.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

LIVE_STATUSES = {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_FIRST_HALF", "STATUS_SECOND_HALF"}
FINAL_STATUSES = {"STATUS_FULL_TIME", "STATUS_FINAL"}


@dataclass
class Goal:
    minute: str
    player: str
    is_penalty: bool = False
    is_own_goal: bool = False
    side: str = ""

    @property
    def minute_sort_key(self) -> int:
        m = (self.minute or "").replace("'", "").strip()
        if not m:
            return 0
        if "+" in m:
            base, extra = m.split("+", 1)
            try:
                return int(base.strip()) * 100 + int(extra.strip())
            except ValueError:
                return 0
        try:
            return int(m) * 100
        except ValueError:
            return 0


@dataclass
class Team:
    name: str
    short: str
    score: str
    is_home: bool
    team_id: str = ""
    goals: list[Goal] = field(default_factory=list)


@dataclass
class Match:
    id: str
    kickoff_utc: datetime
    status_raw: str
    status_label: str
    short_detail: str
    home: Team
    away: Team

    @property
    def is_live(self) -> bool:
        return self.status_raw in LIVE_STATUSES or (self.status_raw.startswith("STATUS_") and "HALF" in self.status_raw)

    @property
    def is_final(self) -> bool:
        return self.status_raw in FINAL_STATUSES

    @property
    def latest_goal(self) -> Goal | None:
        all_goals = list(self.home.goals) + list(self.away.goals)
        if not all_goals:
            return None
        return max(all_goals, key=lambda g: g.minute_sort_key)


@dataclass
class Snapshot:
    fetched_at: datetime
    matches: list[Match]
    source_url: str
    stale: bool = False


def _safe(obj: dict | list | None, *path, default=None):
    cur: Any = obj
    for p in path:
        if cur is None:
            return default
        try:
            cur = cur[p]
        except (KeyError, IndexError, TypeError):
            return default
    return cur if cur is not None else default


def _parse_event(event: dict) -> Match | None:
    try:
        comp = _safe(event, "competitions", 0, default={})
        competitors = _safe(comp, "competitors", default=[]) or []
        home_raw = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
        away_raw = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

        def to_team(raw: dict, is_home: bool) -> Team:
            team = raw.get("team", {}) or {}
            return Team(
                name=team.get("displayName") or team.get("name") or "—",
                short=team.get("abbreviation") or team.get("shortDisplayName") or "—",
                score=str(raw.get("score", "") or ""),
                is_home=is_home,
                team_id=str(team.get("id", "")),
            )

        date_str = event.get("date") or comp.get("date")
        kickoff = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else datetime.now(timezone.utc)
        status = _safe(event, "status", "type", default={}) or {}

        home = to_team(home_raw, True)
        away = to_team(away_raw, False)

        for d in _safe(comp, "details", default=[]) or []:
            if (_safe(d, "type", "text") or "").lower() != "goal":
                continue
            minute = _safe(d, "clock", "displayValue") or ""
            scorer_team_id = str(_safe(d, "team", "id") or "")
            athletes = _safe(d, "athletesInvolved", default=[]) or []
            player_name = ""
            if athletes:
                a0 = athletes[0]
                player_name = a0.get("shortName") or a0.get("displayName") or ""
            goal = Goal(
                minute=minute,
                player=player_name or "—",
                is_penalty=bool(d.get("penaltyKick")),
                is_own_goal=bool(d.get("ownGoal")),
            )
            if scorer_team_id == home.team_id:
                goal.side = "home"
                home.goals.append(goal)
            elif scorer_team_id == away.team_id:
                goal.side = "away"
                away.goals.append(goal)

        return Match(
            id=str(event.get("id", "")),
            kickoff_utc=kickoff,
            status_raw=status.get("name", "STATUS_SCHEDULED"),
            status_label=status.get("description", "Scheduled"),
            short_detail=status.get("shortDetail", ""),
            home=home,
            away=away,
        )
    except Exception:
        return None


class ESPNClient:
    def __init__(self, timeout: float = 8.0):
        self._timeout = timeout
        self._cache: Snapshot | None = None
        self._cache_ts: float = 0.0
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "pi-led/0.1"})

    async def close(self) -> None:
        await self._client.aclose()

    def _ttl_for(self, snapshot: Snapshot | None) -> float:
        if not snapshot:
            return 30.0
        if any(m.is_live for m in snapshot.matches):
            return 30.0
        now = datetime.now(timezone.utc)
        soonest = min((m.kickoff_utc for m in snapshot.matches if m.kickoff_utc > now), default=None)
        if soonest and (soonest - now) < timedelta(hours=1):
            return 60.0
        return 300.0

    async def get(self, force: bool = False) -> Snapshot:
        now_s = time.monotonic()
        if not force and self._cache and (now_s - self._cache_ts) < self._ttl_for(self._cache):
            return self._cache

        now_utc = datetime.now(timezone.utc)
        start = (now_utc - timedelta(days=3)).strftime("%Y%m%d")
        end = (now_utc + timedelta(days=14)).strftime("%Y%m%d")
        url = f"{ESPN_BASE}?dates={start}-{end}&limit=300"
        try:
            r = await self._client.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception:
            if self._cache:
                self._cache.stale = True
                return self._cache
            raise

        events = data.get("events", []) or []
        matches = [m for m in (_parse_event(e) for e in events) if m]
        matches.sort(key=lambda m: m.kickoff_utc)

        snapshot = Snapshot(fetched_at=datetime.now(timezone.utc), matches=matches, source_url=url)
        self._cache = snapshot
        self._cache_ts = now_s
        return snapshot
