"""Data access layer. Only this module knows SQL."""
from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta, timezone

from .db import Database
from .models import FeedItem, Place

_COLS = ("id", "source", "city", "lat", "lon", "precision", "category", "text",
         "author", "url", "embed", "video", "thumb", "ts")


def place_key(name: str) -> str:
    return unicodedata.normalize("NFC", " ".join(name.lower().split()))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FeedRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, items: list[FeedItem]) -> None:
        if not items:
            return
        rows = []
        for it in items:
            d = it.model_dump(mode="json")
            d["ts"] = _iso(it.ts)
            rows.append(tuple(d.get(c) for c in _COLS))
        placeholders = ",".join("?" * len(_COLS))
        updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "id")
        self.db.executemany(
            f"INSERT INTO feed_items({','.join(_COLS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            rows,
        )

    def list(
        self,
        *,
        category: str | None = None,
        city: str | None = None,
        before: datetime | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[FeedItem]:
        # Parameterized query only: filters never reach SQL as text.
        where, params = [], []
        if category:
            where.append("category = ?"); params.append(category)
        if city:
            where.append("city = ?"); params.append(city)
        if before:
            where.append("ts < ?"); params.append(_iso(before))
        if since:
            where.append("ts >= ?"); params.append(_iso(since))
        sql = f"SELECT {','.join(_COLS)} FROM feed_items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        # Most recently collected first: a fresh search keeps its results even
        # when the videos themselves were published long ago.
        sql += " ORDER BY ingested_at DESC, ts DESC LIMIT ?"
        params.append(limit)
        rows = self.db.execute(sql, tuple(params))
        return [FeedItem.model_validate(dict(r)) for r in rows]

    def purge_older_than(self, days: int) -> int:
        cutoff = _iso(datetime.now(timezone.utc) - timedelta(days=days))
        rows = self.db.execute("DELETE FROM feed_items WHERE ingested_at < ? RETURNING id", (cutoff,))
        return len(rows)


class PlaceRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, name: str) -> Place | None:
        rows = self.db.execute("SELECT name,lat,lon FROM places WHERE key = ?", (place_key(name),))
        return Place(**dict(rows[0])) if rows else None

    def save(self, query: str, place: Place, pinned: bool = False) -> None:
        self.db.execute(
            "INSERT INTO places(key,name,lat,lon,pinned) VALUES (?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET pinned = MAX(pinned, excluded.pinned)",
            (place_key(query), place.name, place.lat, place.lon, int(pinned)),
        )

    def pinned(self) -> list[Place]:
        rows = self.db.execute("SELECT name,lat,lon FROM places WHERE pinned = 1 ORDER BY name LIMIT 500")
        return [Place(**dict(r)) for r in rows]


class QuotaRepository:
    def __init__(self, db: Database):
        self.db = db

    def try_consume(self, api: str, daily_limit: int) -> bool:
        """Atomically reserve one call for today; False when the budget is spent."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.db.execute("INSERT OR IGNORE INTO quota_usage(day,api,calls) VALUES (?,?,0)", (day, api))
        rows = self.db.execute(
            "UPDATE quota_usage SET calls = calls + 1 WHERE day = ? AND api = ? AND calls < ? RETURNING calls",
            (day, api, daily_limit),
        )
        return bool(rows)


class MetaRepository:
    """Small key/value store for app state (e.g. last collector run)."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str) -> str | None:
        rows = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
