"""Default collection: keeps the globe populated without any user search.

Every `refresh_hours`, fetches the latest YouTube videos for each default
city (NIAN_DEFAULT_CITIES). The last run is stored in the database, so
restarting the server does not spend quota again. Each city costs one
search (100 quota units) and counts against the shared daily budget,
which always leaves room for user searches.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool

log = logging.getLogger("nian.collector")
LAST_RUN = "collector.default.last_run"
RESERVED_FOR_USERS = 20  # daily searches never used by the background collector


async def collect_defaults(ctx, cities: list[str], budget: int) -> int:
    """One pass over the default cities. Returns the number of items stored."""
    since = datetime.now(timezone.utc) - timedelta(days=3)
    total = 0
    for name in cities:
        if not await run_in_threadpool(ctx.quota.try_consume, "youtube.search", max(1, budget - RESERVED_FOR_USERS)):
            log.warning("daily budget reached, default collection paused")
            break
        place = await run_in_threadpool(ctx.places.get, name) or await ctx.geocoder.geocode(name)
        if not place:
            continue
        try:
            items = await ctx.youtube.search("", place, 10, published_after=since)
        except Exception as exc:  # CollectorError or unexpected: log and go on
            log.warning("default collection failed for %s: %s", name, exc)
            continue
        await ctx.ingest(items)
        total += len(items)
    return total


async def run_collector(ctx, cities: list[str], budget: int, refresh_hours: int) -> None:
    while True:
        try:
            last = await run_in_threadpool(ctx.meta.get, LAST_RUN)
            due = not last or datetime.fromisoformat(last) < datetime.now(timezone.utc) - timedelta(hours=refresh_hours)
            if due:
                n = await collect_defaults(ctx, cities, budget)
                await run_in_threadpool(ctx.meta.set, LAST_RUN, datetime.now(timezone.utc).isoformat())
                log.info("default collection: %d items for %d cities", n, len(cities))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("default collection crashed")
        await asyncio.sleep(600)  # check again in 10 minutes
