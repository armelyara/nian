"""Demo feed generator, enabled only with NIAN_DEMO=1.

Runs as ONE background task that writes to the DB and publishes to the
broker, instead of one random generator per connected client. It produces
the five networks of the design (X, Instagram, TikTok, Facebook, YouTube),
each with the content shape that network uses."""
from __future__ import annotations

import asyncio
import logging
import random
import secrets

from ..models import FeedItem, Place

log = logging.getLogger("nian.demo")

VIDEOS = [
    "https://media.w3.org/2010/05/sintel/trailer_hd.mp4",
    "https://media.w3.org/2010/05/bunny/trailer.mp4",
    "https://media.w3.org/2010/05/video/movie_300.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
]
SNIPPETS = [
    ("Concert tonight, the crowd is starting to arrive", "Concerts"),
    ("Main stage, the show is on", "Concerts"),
    ("Packed crowd on the main square", "Protests"),
    ("Rally in front of city hall", "Protests"),
    ("Slowdown reported on the main road", "Incidents"),
    ("Heavy traffic approaching downtown", "Incidents"),
    ("Developer meetup, live demo in progress", "Tech"),
    ("Tonight's line-up and opening hours", "Concerts"),
]
# (source, weight, carries a video)
NETWORKS = [("X", 3, False), ("TikTok", 3, True), ("Instagram", 2, False), ("Facebook", 1, False), ("YouTube", 1, True)]
AUTHORS = ["@live_report", "@onsite_cam", "@city_pulse", "@field_stream", "@eyewitness"]


def demo_item(places: list[Place]) -> FeedItem:
    p = random.choice(places)
    text, cat = random.choice(SNIPPETS)
    source, _, has_video = random.choices(NETWORKS, weights=[n[1] for n in NETWORKS])[0]
    return FeedItem(
        id=f"demo_{secrets.token_hex(6)}", source=source, city=p.name,
        lat=p.lat + random.uniform(-0.05, 0.05), lon=p.lon + random.uniform(-0.05, 0.05),
        precision="city", category=cat, text=f"[DEMO] {text}",
        author=random.choice(AUTHORS), video=random.choice(VIDEOS) if has_video else None,
    )


async def run_demo(get_places, on_items, interval: float = 2.5, warmup: int = 40) -> None:
    # Initial burst so the map is not empty on first launch.
    places = await get_places()
    if places and warmup:
        await on_items([demo_item(places) for _ in range(warmup)])
    while True:
        try:
            places = await get_places()
            if places:
                await on_items([demo_item(places)])
        except asyncio.CancelledError:
            raise
        except Exception:  # keep the loop alive, but never silently
            log.exception("demo tick failed")
        await asyncio.sleep(interval)
