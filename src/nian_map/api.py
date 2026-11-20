"""HTTP API v1. Handlers stay thin: validation here, logic in services."""
from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from .broker import TooManySubscribers
from .config import settings
from .models import CATEGORIES, FeedPage, Meta, Place, SearchResult
from .security import limit_search, require_token
from .services.youtube import CollectorError

router = APIRouter(prefix="/api/v1")
CategoryParam = Query(None, max_length=32)


class TTLCache:
    """Small bounded TTL cache for search results (saves YouTube quota)."""

    def __init__(self, ttl: float = 600, size: int = 256):
        self.ttl, self.size = ttl, size
        self._d: OrderedDict[str, tuple[float, SearchResult]] = OrderedDict()

    def get(self, k: str) -> SearchResult | None:
        hit = self._d.get(k)
        if not hit or time.monotonic() - hit[0] > self.ttl:
            self._d.pop(k, None)
            return None
        self._d.move_to_end(k)
        return hit[1]

    def put(self, k: str, v: SearchResult) -> None:
        self._d[k] = (time.monotonic(), v)
        self._d.move_to_end(k)
        while len(self._d) > self.size:
            self._d.popitem(last=False)


search_cache = TTLCache()


def ctx(request: Request):
    return request.app.state.ctx


@router.get("/meta", response_model=Meta)
def meta(c=Depends(ctx)):
    return Meta(categories=CATEGORIES, search_enabled=c.youtube.enabled, token_required=bool(settings.api_token))


@router.get("/places", response_model=list[Place])
def places(c=Depends(ctx)):
    return c.places.pinned()


@router.get("/feeds", response_model=FeedPage)
def feeds(
    category: str | None = CategoryParam,
    city: str | None = Query(None, max_length=120),
    before: datetime | None = None,
    since: datetime | None = None,
    limit: int = Query(100, ge=1, le=settings.max_feed_limit),
    c=Depends(ctx),
):
    if category and category not in CATEGORIES:
        raise HTTPException(422, "Unknown category.")
    return FeedPage(items=c.feeds.list(category=category, city=city, before=before, since=since, limit=limit))


@router.get("/stream")
async def stream(request: Request, c=Depends(ctx)):
    try:
        sub = c.broker.subscribe()
        queue = sub.__enter__()
    except TooManySubscribers:
        raise HTTPException(503, "Too many live connections.", headers={"Retry-After": "30"})

    async def gen():
        try:
            yield "retry: 5000\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # heartbeat keeps proxies from closing the socket
        finally:
            sub.__exit__(None, None, None)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/search", response_model=SearchResult,
            dependencies=[Depends(require_token), Depends(limit_search)])
async def search(
    q: str = Query("", max_length=120),
    place: str = Query("", max_length=80),
    limit: int = Query(12, ge=1, le=25),
    c=Depends(ctx),
):
    q, place = q.strip(), place.strip()
    if not q and not place:
        raise HTTPException(422, "Empty query.")
    if not c.youtube.enabled:
        raise HTTPException(503, "Search disabled: NIAN_YOUTUBE_KEY is missing.")

    key = json.dumps([q.lower(), place.lower(), limit])
    cached = search_cache.get(key)
    if cached:
        return cached.model_copy(update={"cached": True})

    if not await run_in_threadpool(c.quota.try_consume, "youtube.search", settings.youtube_daily_search_budget):
        raise HTTPException(429, "Daily search budget reached.")

    geo = await c.geocoder.geocode(place) if place else None
    try:
        items = await c.youtube.search(q, geo, limit)
    except CollectorError as exc:
        raise HTTPException(502, str(exc))

    await c.ingest(items)
    result = SearchResult(items=items, place=geo)
    search_cache.put(key, result)
    return result


# Legacy aliases kept for the v1 front / Indice integration.
legacy = APIRouter(prefix="/api/geospatial", include_in_schema=False)


@legacy.get("/snapshot")
def legacy_snapshot(c=Depends(ctx)):
    return {"items": [i.model_dump(mode="json") for i in c.feeds.list(limit=50)]}


legacy.add_api_route("/stream", stream, methods=["GET"])
