"""YouTube Data API v3 collector."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

import httpx

from ..models import YOUTUBE_EMBED_PREFIX, FeedItem, Place
from .categorize import categorize

log = logging.getLogger("nian.youtube")
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class CollectorError(Exception):
    """Upstream failure; message is safe to show to users."""


def spread(item_id: str, lat: float, lon: float, radius: float = 0.03) -> tuple[float, float]:
    """Deterministic offset so markers sharing a city centroid don't overlap.
    Unlike random jitter, the same item always lands on the same spot and the
    item is flagged precision='city' so the UI never claims an exact location."""
    h = hashlib.sha256(item_id.encode()).digest()
    dx = (h[0] / 255 - 0.5) * 2 * radius
    dy = (h[1] / 255 - 0.5) * 2 * radius
    return max(-90.0, min(90.0, lat + dy)), ((lon + dx + 180) % 360) - 180


class YouTubeCollector:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self.client = client
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _terms(q: str, place: Place | None) -> str:
        # Avoid "France election France": only append the place if absent.
        if place and place.name.lower() not in q.lower():
            return f"{q} {place.name}".strip()
        return q

    async def search(self, q: str, place: Place | None, limit: int,
                     published_after: datetime | None = None) -> list[FeedItem]:
        params = {
            "part": "snippet", "type": "video", "videoEmbeddable": "true",
            "maxResults": str(limit), "q": self._terms(q, place),
            "order": "date", "safeSearch": "moderate",
        }
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Note: the API's location/locationRadius filter only returns geotagged
        # videos (a small minority), so the place is used as a text term instead.
        try:
            # Key sent as a header, never in the URL (keeps it out of proxy/access logs).
            r = await self.client.get(SEARCH_URL, params=params,
                                      headers={"X-Goog-Api-Key": self.api_key}, timeout=10.0)
        except httpx.HTTPError as exc:
            log.error("youtube network error: %s", exc)
            raise CollectorError("YouTube service unreachable.") from exc
        if r.status_code == 403:
            log.error("youtube 403: %s", r.text[:300])
            raise CollectorError("YouTube quota exhausted or key rejected.")
        if r.status_code >= 400:
            log.error("youtube %s: %s", r.status_code, r.text[:300])
            raise CollectorError("YouTube service error.")

        center = place or Place(name="World", lat=20.0, lon=0.0)
        items: list[FeedItem] = []
        for raw in r.json().get("items", []):
            vid = (raw.get("id") or {}).get("videoId", "")
            if not VIDEO_ID_RE.match(vid):
                continue
            sn = raw.get("snippet") or {}
            item_id = f"yt_{vid}"
            lat, lon = spread(item_id, center.lat, center.lon)
            title = (sn.get("title") or "")[:500]
            try:
                ts = datetime.fromisoformat((sn.get("publishedAt") or "").replace("Z", "+00:00"))
            except ValueError:
                ts = None
            thumb = ((sn.get("thumbnails") or {}).get("medium") or {}).get("url") or None
            data = dict(
                id=item_id, source="YouTube", city=center.name,
                lat=lat, lon=lon, precision="city" if place else "region",
                category=categorize(f"{q} {title}"), text=title,
                author=(sn.get("channelTitle") or "")[:120],
                url=f"https://www.youtube.com/watch?v={vid}",
                embed=f"{YOUTUBE_EMBED_PREFIX}{vid}?autoplay=1&mute=1&playsinline=1&modestbranding=1",
                thumb=thumb if thumb and thumb.startswith("https://") else None,
            )
            if ts:
                data["ts"] = ts
            items.append(FeedItem(**data))
        return items
