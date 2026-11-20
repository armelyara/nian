"""SQLite storage (WAL mode). The schema mirrors docs/schema.postgres.sql so
the repository can move to Postgres/PostGIS without changing callers."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_items (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    city         TEXT NOT NULL,
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    precision    TEXT NOT NULL DEFAULT 'city',
    category     TEXT NOT NULL,
    text         TEXT NOT NULL DEFAULT '',
    author       TEXT NOT NULL DEFAULT '',
    url          TEXT,
    embed        TEXT,
    video        TEXT,
    thumb        TEXT,
    ts           TEXT NOT NULL,              -- ISO-8601 UTC, published time
    ingested_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS ix_feed_ts        ON feed_items(ts DESC);
CREATE INDEX IF NOT EXISTS ix_feed_cat_ts    ON feed_items(category, ts DESC);
CREATE INDEX IF NOT EXISTS ix_feed_city_ts   ON feed_items(city, ts DESC);
CREATE INDEX IF NOT EXISTS ix_feed_ingested  ON feed_items(ingested_at);

CREATE TABLE IF NOT EXISTS places (
    key        TEXT PRIMARY KEY,             -- normalized lookup key
    name       TEXT NOT NULL,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    pinned     INTEGER NOT NULL DEFAULT 0,   -- 1 = shown on the globe by default
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_usage (
    day     TEXT NOT NULL,
    api     TEXT NOT NULL,
    calls   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, api)
);
"""

SEED_PLACES = [
    # Cities shown in the design (Monde + Côte d'Ivoire), plus the v1 set.
    ("abidjan", "Abidjan", 5.3599, -4.0083),
    ("bouaké", "Bouaké", 7.6906, -5.0300),
    ("yamoussoukro", "Yamoussoukro", 6.8276, -5.2893),
    ("korhogo", "Korhogo", 9.4580, -5.6296),
    ("daloa", "Daloa", 6.8774, -6.4502),
    ("san-pédro", "San-Pédro", 4.7485, -6.6363),
    ("man", "Man", 7.4125, -7.5538),
    ("dakar", "Dakar", 14.7167, -17.4677),
    ("lagos", "Lagos", 6.5244, 3.3792),
    ("le caire", "Le Caire", 30.0444, 31.2357),
    ("nairobi", "Nairobi", -1.2921, 36.8219),
    ("johannesburg", "Johannesburg", -26.2041, 28.0473),
    ("londres", "Londres", 51.5072, -0.1276),
    ("paris", "Paris", 48.8566, 2.3522),
    ("montréal", "Montréal", 45.5019, -73.5674),
    ("tokyo", "Tokyo", 35.6762, 139.6503),
    ("singapour", "Singapour", 1.3521, 103.8198),
]


class Database:
    """Thread-safe wrapper: one connection guarded by a lock is plenty for
    an MVP (SQLite serializes writes anyway). Calls run in FastAPI's
    threadpool via sync route handlers or run_in_threadpool."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.executemany(
                "INSERT OR IGNORE INTO places(key,name,lat,lon,pinned) VALUES (?,?,?,?,1)", SEED_PLACES
            )

    def execute(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                self._conn.executemany(sql, rows)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()
