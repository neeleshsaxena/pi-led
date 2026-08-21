"""Thin ESPN client for the English Premier League (eng.1) — keyless.

Uses the `site.web.api.espn.com` host (the older `site.api.espn.com` host is now
Akamai-blocked with 403s). Exposes three small reads used by the panel:
  - scoreboard(dates) : matches in a window (today by default, or a date range)
  - upcoming(days)    : scheduled fixtures over the next N days
  - standings()       : the league table

Returns plain dicts; short per-call caches keep the render loop cheap and polite.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import httpx

HOST = "https://site.web.api.espn.com"
SCOREBOARD = HOST + "/apis/site/v2/sports/soccer/{league}/scoreboard"
STANDINGS = HOST + "/apis/v2/sports/soccer/{league}/standings"
_HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


class EplClient:
    def __init__(self, league: str = "eng.1", timeout: float = 8.0):
        self.league = league
        self._client = httpx.AsyncClient(timeout=timeout, headers=_HDRS, follow_redirects=True)
        self._cache: dict[str, tuple[float, dict]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def _json(self, url: str, params: dict, key: str, ttl: float) -> dict | None:
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        try:
            r = await self._client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            self._cache[key] = (now, data)
            return data
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else None

    @staticmethod
    def _parse_events(data: dict | None) -> list[dict]:
        out: list[dict] = []
        for e in (data or {}).get("events", []) or []:
            comp = (e.get("competitions") or [{}])[0]
            st = (e.get("status") or {}).get("type") or {}
            sides: dict[str, dict] = {}
            for c in comp.get("competitors", []):
                t = c.get("team") or {}
                sides[c.get("homeAway", "")] = {
                    "abbr": (t.get("abbreviation") or "").upper(),
                    "name": t.get("shortDisplayName") or "",
                    "color": t.get("color") or "",
                    "score": _int(c.get("score")),
                }
            out.append(
                {
                    "date": _dt(e.get("date") or ""),
                    "state": st.get("state") or "pre",  # pre | in | post
                    "completed": bool(st.get("completed")),
                    "detail": st.get("shortDetail") or "",
                    "clock": (e.get("status") or {}).get("displayClock") or "",
                    "home": sides.get("home", {}),
                    "away": sides.get("away", {}),
                }
            )
        out.sort(key=lambda m: m["date"] or datetime.max.replace(tzinfo=timezone.utc))
        return out

    async def scoreboard(self, dates: str | None = None, ttl: float = 45.0) -> list[dict]:
        params = {"dates": dates} if dates else {}
        data = await self._json(
            SCOREBOARD.format(league=self.league), params, f"sb:{self.league}:{dates or 'now'}", ttl
        )
        return self._parse_events(data)

    async def upcoming(self, days: int = 12, ttl: float = 600.0) -> list[dict]:
        now = datetime.now(timezone.utc)
        rng = f"{now:%Y%m%d}-{now + timedelta(days=days):%Y%m%d}"
        return [m for m in await self.scoreboard(dates=rng, ttl=ttl) if m["state"] == "pre"]

    async def standings(self, ttl: float = 600.0) -> list[dict]:
        data = await self._json(STANDINGS.format(league=self.league), {}, f"st:{self.league}", ttl)
        if not data:
            return []
        entries = None
        if data.get("children"):
            entries = (data["children"][0].get("standings") or {}).get("entries")
        elif data.get("standings"):
            entries = data["standings"].get("entries")
        rows: list[dict] = []
        for e in entries or []:
            t = e.get("team") or {}
            stats = {s.get("name"): s.get("value") for s in e.get("stats", [])}
            rows.append(
                {
                    "rank": _int(stats.get("rank")),
                    "abbr": (t.get("abbreviation") or "").upper(),
                    "name": t.get("shortDisplayName") or "",
                    "played": _int(stats.get("gamesPlayed")),
                    "wins": _int(stats.get("wins")),
                    "ties": _int(stats.get("ties")),
                    "losses": _int(stats.get("losses")),
                    "gd": _int(stats.get("pointDifferential")),
                    "points": _int(stats.get("points")),
                }
            )
        rows.sort(key=lambda r: r["rank"] or 99)
        return rows
