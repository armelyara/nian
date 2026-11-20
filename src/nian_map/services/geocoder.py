"""Nominatim geocoder that respects the OSM usage policy:
max 1 request/second, identifying User-Agent, results cached (DB + memory)."""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
from fastapi.concurrency import run_in_threadpool

from ..models import Place
from ..repository import PlaceRepository

log = logging.getLogger("nian.geocoder")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class Geocoder:
    def __init__(self, places: PlaceRepository, client: httpx.AsyncClient, user_agent: str):
        self.places = places
        self.client = client
        self.user_agent = user_agent
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def geocode(self, query: str) -> Place | None:
        """Free-text input like "France élection": try the full string, then at
        most two single-word fallbacks (last, first). Bounded on purpose:
        the v1 loop could fire one upstream call per word."""
        words = [w for w in query.split() if len(w) >= 3]
        candidates = list(dict.fromkeys([query.strip(), *words[-1:], *words[:1]]))[:3]
        for cand in candidates:
            if cand and (place := await self._lookup(cand)):
                if cand != query.strip():
                    await run_in_threadpool(self.places.save, query, place, False)
                return place
        return None

    async def _lookup(self, query: str) -> Place | None:
        cached = await run_in_threadpool(self.places.get, query)
        if cached:
            return cached
        async with self._lock:  # serialize upstream calls: 1 req/s max
            wait = 1.0 - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
            try:
                r = await self.client.get(
                    NOMINATIM_URL,
                    params={"q": query, "format": "jsonv2", "limit": 1},
                    headers={"User-Agent": self.user_agent, "Accept-Language": "fr"},
                    timeout=6.0,
                )
                r.raise_for_status()
                data = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("geocode failed for %r: %s", query, exc)
                return None
        if not data:
            return None
        hit = data[0]
        name = (hit.get("name") or hit.get("display_name") or query).split(",")[0][:120]
        place = Place(name=name, lat=float(hit["lat"]), lon=float(hit["lon"]))
        await run_in_threadpool(self.places.save, query, place, True)
        return place
