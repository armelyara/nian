"""Application factory and wiring (composition root)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import legacy, router
from .broker import Broker
from .config import Settings, settings as default_settings
from .db import Database
from .models import FeedItem
from . import __version__
from .repository import FeedRepository, MetaRepository, PlaceRepository, QuotaRepository
from .security import SecurityHeadersMiddleware
from .services.collector import run_collector
from .services.demo import run_demo
from .services.geocoder import Geocoder
from .services.youtube import YouTubeCollector

log = logging.getLogger("nian")


@dataclass
class AppContext:
    db: Database
    feeds: FeedRepository
    places: PlaceRepository
    quota: QuotaRepository
    meta: MetaRepository
    broker: Broker
    geocoder: Geocoder
    youtube: YouTubeCollector

    async def ingest(self, items: list[FeedItem]) -> None:
        """Single write path: persist, then fan out to live clients."""
        if not items:
            return
        await run_in_threadpool(self.feeds.upsert, items)
        for it in items:
            self.broker.publish(json.dumps(it.model_dump(mode="json"), ensure_ascii=False))


def create_app(cfg: Settings = default_settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(cfg.db_path)
        client = httpx.AsyncClient(follow_redirects=False, limits=httpx.Limits(max_connections=20))
        places = PlaceRepository(db)
        c = AppContext(
            db=db, feeds=FeedRepository(db), places=places, quota=QuotaRepository(db), meta=MetaRepository(db),
            broker=Broker(max_subscribers=cfg.max_sse_clients),
            geocoder=Geocoder(places, client, cfg.geocoder_user_agent),
            youtube=YouTubeCollector(client, cfg.youtube_key),
        )
        app.state.ctx = c
        purged = await run_in_threadpool(c.feeds.purge_older_than, cfg.retention_days)
        log.info("startup: purged %d expired items, search=%s demo=%s", purged, c.youtube.enabled, cfg.demo)
        tasks = []
        if cfg.demo:
            tasks.append(asyncio.create_task(run_demo(lambda: run_in_threadpool(places.pinned), c.ingest)))
        if c.youtube.enabled and cfg.default_cities:
            # Real content by default: latest videos for the default cities.
            tasks.append(asyncio.create_task(run_collector(
                c, cfg.default_cities, cfg.youtube_daily_search_budget, cfg.refresh_hours)))
        try:
            yield
        finally:
            for t in tasks:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await t
            await client.aclose()
            db.close()

    app = FastAPI(
        title="Nian", version=__version__, lifespan=lifespan,
        docs_url="/docs" if cfg.debug else None, redoc_url=None,
        openapi_url="/openapi.json" if cfg.debug else None,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if cfg.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=cfg.allowed_hosts)

    app.include_router(router)
    app.include_router(legacy)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    index = cfg.static_dir / "index.html"

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    # Only the dedicated static/ folder is public — never the project root.
    app.mount("/static", StaticFiles(directory=cfg.static_dir), name="static")
    return app


app = create_app()
