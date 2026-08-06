"""Local news headlines via Google News RSS (free, no API key).

`headlines(place)` returns recent headlines for a location — it tries the
location "geo" section first, then falls back to a plain search for the place.
Titles are cleaned of the trailing " - Source". Cached with a TTL so the render
loop stays cheap; serves the last good value on any error.
"""
from __future__ import annotations

import time
from urllib.parse import quote
from xml.etree import ElementTree as ET

import httpx

GEO_URL = "https://news.google.com/rss/headlines/section/geo/{place}"
SEARCH_URL = "https://news.google.com/rss/search"
_PARAMS = {"hl": "en-US", "gl": "US", "ceid": "US:en"}


class NewsClient:
    def __init__(self, timeout: float = 8.0):
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "pi-led/0.1"}
        )
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._ttl = 900.0  # 15 min — headlines don't churn faster than the panel needs

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _clean(title: str) -> str:
        # Google News titles are "Headline - Source"; drop the source tail.
        if " - " in title:
            head, _, src = title.rpartition(" - ")
            if head and len(src) <= 40:
                title = head
        return " ".join(title.split()).strip()

    def _parse(self, xml: str, limit: int) -> list[str]:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        out: list[str] = []
        for item in root.iter("item"):
            t = self._clean(item.findtext("title") or "")
            if t:
                out.append(t)
            if len(out) >= limit:
                break
        return out

    async def headlines(self, place: str, limit: int = 8) -> list[str]:
        place = (place or "").strip() or "San Francisco"
        now = time.monotonic()
        hit = self._cache.get(place)
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        try:
            r = await self._client.get(GEO_URL.format(place=quote(place)), params=_PARAMS)
            r.raise_for_status()
            items = self._parse(r.text, limit)
            if not items:  # small towns may have no geo section — search instead
                r = await self._client.get(SEARCH_URL, params={"q": place, **_PARAMS})
                r.raise_for_status()
                items = self._parse(r.text, limit)
            if items:
                self._cache[place] = (now, items)
            return items or (hit[1] if hit else [])
        except Exception:  # noqa: BLE001 - a bad fetch must not break the panel
            return hit[1] if hit else []
