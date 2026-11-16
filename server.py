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
import urllib.parse
import urllib.request

from fastapi import FastAPI, Query
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


YT_KEY = os.environ.get("NIAN_YOUTUBE_KEY") or os.environ.get("YOUTUBE_API_KEY") or ""
_geo_cache = {}


def _geocode(place):
    if not place:
        return None
    k = place.strip().lower()
    for cname, (la, lo) in CITIES.items():
        if cname.lower() in k:
            return (la, lo)
    cands = [place] + [w for w in place.split() if len(w) >= 3]
    for cand in cands:
        ck = cand.strip().lower()
        if ck in _geo_cache:
            return _geo_cache[ck]
        try:
            u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": cand, "format": "json", "limit": 1})
            req = urllib.request.Request(u, headers={"User-Agent": "Nian/1.0 (OSINT demo)"})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.load(r)
            if d:
                res = (float(d[0]["lat"]), float(d[0]["lon"]))
                _geo_cache[ck] = res
                return res
        except Exception:
            pass
    return None


def _guess_cat(t):
    t = (t or "").lower()
    if any(w in t for w in ["concert", "festival", "show", "musi"]):
        return "Concerts"
    if any(w in t for w in ["manif", "election", "campagne", "greve", "protest", "marche", "presidentielle"]):
        return "Manifestations"
    if any(w in t for w in ["incident", "accident", "attaque", "explosion", "fusillade", "crash", "emeute"]):
        return "Incidents"
    return "Tech"


@app.get("/api/geospatial/search")
def search_feeds(q: str = Query(""), place: str = Query(""), max: int = Query(12)):
    # Real collector: YouTube Data API v3. Needs env NIAN_YOUTUBE_KEY.
    if not YT_KEY:
        return JSONResponse({"error": "NIAN_YOUTUBE_KEY manquante (voir README).", "items": []}, status_code=400)
    coords = _geocode(place) or (20.0, 0.0)
    try:
        params = {"part": "snippet", "type": "video", "videoEmbeddable": "true",
                  "maxResults": str(min(max, 25)), "q": (q + " " + place).strip(), "order": "date", "key": YT_KEY}
        u = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(u, headers={"User-Agent": "Nian/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except Exception as e:
        return JSONResponse({"error": "YouTube API: " + str(e), "items": []}, status_code=502)
    items = []
    for it in data.get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        if not vid:
            continue
        sn = it.get("snippet") or {}
        thumb = ((sn.get("thumbnails") or {}).get("medium") or {}).get("url", "")
        items.append({
            "id": "yt_" + vid, "source": "YouTube", "city": place or (sn.get("channelTitle") or "-"),
            "lat": coords[0] + random.uniform(-0.05, 0.05), "lon": coords[1] + random.uniform(-0.05, 0.05),
            "category": _guess_cat((q or "") + " " + (sn.get("title") or "")),
            "text": sn.get("title") or "", "author": sn.get("channelTitle") or "",
            "url": "https://www.youtube.com/watch?v=" + vid,
            "embed": "https://www.youtube.com/embed/" + vid + "?autoplay=1&mute=1&loop=1&playlist=" + vid + "&controls=0&playsinline=1&modestbranding=1",
            "thumb": thumb,
            "ts": (sn.get("publishedAt") or "").replace("T", " ").replace("Z", "")[:19],
        })
    return {"items": items, "place": place, "lat": coords[0], "lon": coords[1]}


if os.path.isdir(HERE):
    app.mount("/static", StaticFiles(directory=HERE), name="static")
