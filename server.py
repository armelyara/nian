"""Nian - standalone live map module (FastAPI).

  GET /                         -> the map UI
  GET /world.geojson            -> land outlines for the globe
  GET /api/geospatial/snapshot  -> initial batch of feed items
  GET /api/geospatial/stream    -> SSE stream of new feed items (text/event-stream)

Feed item shape: { id, source, city, lat, lon, category, text, author, url, video, ts }.
Replace _demo_item() with a real public-feed collector later; the UI is unchanged.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="Nian")

CITIES = {
    "Singapour": (1.3521, 103.8198),
    "Abidjan": (5.3599, -4.0083),
    "Montréal": (45.5019, -73.5674),
    "Paris": (48.8566, 2.3522),
    "Tokyo": (35.6762, 139.6503),
}
CATS = ["Concerts", "Manifestations", "Incidents", "Tech"]
SOURCES = ["X", "Instagram", "TikTok", "YouTube"]
AUTHORS = ["@live_report", "@onsite_cam", "@city_pulse", "@field_stream", "@eyewitness"]
VIDEO_URLS = [
    "https://www.w3schools.com/html/mov_bbb.mp4",
    "https://media.w3.org/2010/05/sintel/trailer_hd.mp4",
    "https://media.w3.org/2010/05/bunny/trailer.mp4",
    "https://media.w3.org/2010/05/video/movie_300.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
]
SNIPPETS = [
    "Foule compacte sur la place centrale, direct",
    "Scène principale, ambiance en cours",
    "Rassemblement et slogans en direct",
    "Ralentissement signalé sur l'axe principal",
    "File d'attente massive à l'entrée",
    "Meetup développeurs, démo live",
    "Annonce officielle relayée sur place",
]


def _demo_item():
    city = random.choice(list(CITIES))
    lat, lon = CITIES[city]
    return {
        "id": "f%d" % random.randint(100000, 999999),
        "source": random.choice(SOURCES),
        "city": city,
        "lat": lat + random.uniform(-0.06, 0.06),
        "lon": lon + random.uniform(-0.06, 0.06),
        "category": random.choice(CATS),
        "text": random.choice(SNIPPETS),
        "author": random.choice(AUTHORS),
        "url": "",
        "video": random.choice(VIDEO_URLS),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/")
async def index():
    p = os.path.join(HERE, "index.html")
    return FileResponse(p) if os.path.isfile(p) else JSONResponse({"detail": "index.html not found"}, status_code=404)


@app.get("/world.geojson")
async def world():
    p = os.path.join(HERE, "world.geojson")
    return FileResponse(p, media_type="application/json") if os.path.isfile(p) else JSONResponse({"detail": "not found"}, status_code=404)


@app.get("/api/geospatial/snapshot")
async def snapshot():
    return {"items": [_demo_item() for _ in range(9)]}


@app.get("/api/geospatial/stream")
async def stream():
    async def gen():
        while True:
            yield "data: " + json.dumps(_demo_item()) + "\n\n"
            await asyncio.sleep(2.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


if os.path.isdir(HERE):
    app.mount("/static", StaticFiles(directory=HERE), name="static")
