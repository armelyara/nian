"""Nian - standalone geospatial live map module (FastAPI).

Serves the single-page map and a demo geospatial feed. The front talks to:
  GET /                         -> the map UI
  GET /world.geojson            -> land outlines for the globe
  GET /api/geospatial/snapshot  -> initial batch of feed items
  GET /api/geospatial/stream    -> SSE stream of new feed items (text/event-stream)

Replace _demo_item() with a real collector (public social/event feeds) later.
The UI stays identical: it only consumes the JSON shape below.
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
    "Montreal": (45.5019, -73.5674),
    "Paris": (48.8566, 2.3522),
    "Tokyo": (35.6762, 139.6503),
}
CATS = ["Concerts", "Manifestations", "Incidents", "Tech"]
SOURCES = ["X", "Instagram", "TikTok", "YouTube"]
SNIPPETS = [
    "Foule compacte signalee sur la place centrale",
    "Direct video: scene principale",
    "Rassemblement en cours, slogans",
    "Coupure reseau signalee par plusieurs comptes",
    "Annonce officielle relayee",
    "File d'attente massive a l'entree",
    "Demo tech / meetup developpeurs",
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
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/")
async def index():
    p = os.path.join(HERE, "index.html")
    if os.path.isfile(p):
        return FileResponse(p)
    return JSONResponse({"detail": "index.html not found"}, status_code=404)


@app.get("/world.geojson")
async def world():
    p = os.path.join(HERE, "world.geojson")
    if os.path.isfile(p):
        return FileResponse(p, media_type="application/json")
    return JSONResponse({"detail": "world.geojson not found"}, status_code=404)


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
